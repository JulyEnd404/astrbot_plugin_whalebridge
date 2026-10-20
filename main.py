"""Experimental AstrBot platform adapter for the MimicWX HTTP/UI transport."""

import asyncio
import base64
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import aiohttp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import At, Image, Plain, Reply
from astrbot.api.platform import (
    AstrBotMessage,
    Group,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
)
from astrbot.api.star import Context, Star, register
from astrbot.core.platform.register import register_platform_adapter
from astrbot.core.star.star_tools import StarTools

from .codec import Ledger, group_id, identity, normalize
from .config import settings_from
from .media import MAX_INPUT_BYTES, prepare_image

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class MimicWXEvent(AstrMessageEvent):
    def __init__(self, message_str, message_obj, platform_meta, session_id, adapter):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.adapter = adapter

    async def send(self, message: MessageChain):
        await self.adapter.send_chain(self.get_group_id(), message)
        await super().send(message)


@register_platform_adapter(
    "mimicwx",
    "实验性 MimicWX HTTP 微信通道，请先阅读风险说明",
    default_config_tmpl={
        "type": "mimicwx",
        "enable": False,
        "id": "whalebridge-wechat",
        "risk_acknowledged": False,
        "api_url": "http://127.0.0.1:8899",
        "api_token_env": "MIMICWX_API_TOKEN",
        "api_token": "",
        "groups": [],
        "self_name": "你的机器人昵称",
        "mention_names": ["你的机器人昵称"],
        "unknown_sender_policy": "mention_only",
        "poll_interval": 2.0,
        "discard_startup_backlog": True,
    },
    adapter_display_name="鲸桥 WhaleBridge（实验性微信通道）",
    support_streaming_message=False,
    config_metadata={
        "api_token": {
            "type": "string",
            "description": "API token（推荐改用环境变量）",
            "secret": True,
        },
        "api_token_env": {
            "type": "string",
            "description": "AstrBot进程内保存API token的环境变量名称",
        },
        "risk_acknowledged": {"type": "bool", "description": "已阅读README和DISCLAIMER并理解风险"},
    },
)
class MimicWXAdapter(Platform):
    _active_origins: set[str] = set()

    def __init__(self, platform_config, platform_settings, event_queue):
        super().__init__(platform_config, event_queue)
        self.settings = settings_from(platform_config)
        self.origin = self.settings.api_url.lower()
        if self.origin in self._active_origins:
            raise ValueError("Only one adapter may consume messages from a MimicWX origin")
        self.groups = {group_id(g): g for g in self.settings.groups}
        self.self_id = (
            "mimicwx-bot-" + hashlib.sha256(self.settings.platform_id.encode()).hexdigest()[:12]
        )
        self.state_dir = StarTools.get_data_dir("astrbot_plugin_whalebridge") / (
            "instance_" + hashlib.sha256(self.settings.platform_id.encode()).hexdigest()[:12]
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(self.state_dir / "bridge.sqlite3")
        self.client = None
        self.shutdown_event = asyncio.Event()
        self.send_lock = asyncio.Lock()
        self.image_lock = asyncio.Lock()
        self.available = set()
        self.bootstrapped = False
        self.started = time.time()
        self.terminated = False
        self.counts = {
            "received": 0,
            "anonymous": 0,
            "sent_text": 0,
            "sent_image": 0,
            "unverified_sends": 0,
            "errors": 0,
        }
        self._active_origins.add(self.origin)

    def meta(self):
        return PlatformMetadata(
            name="mimicwx",
            description="MimicWX HTTP 微信通道",
            id=self.settings.platform_id,
            support_streaming_message=False,
        )

    async def api(self, path, body=None):
        if self.terminated:
            raise RuntimeError("adapter_stopped")
        if self.client is None or self.client.closed:
            self.client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=25),
                headers={"Authorization": "Bearer " + self.settings.api_token},
                trust_env=False,
            )
        async with self.client.request(
            "GET" if body is None else "POST",
            self.settings.api_url + path,
            json=body,
            allow_redirects=False,
        ) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("transport_http_error_" + str(response.status))
            raw = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("transport_response_too_large")
            return json.loads(raw)

    def write_health(self, status):
        value = dict(
            self.counts,
            status=status,
            updated_at=int(time.time()),
            uptime_sec=int(time.time() - self.started),
            configured_groups=len(self.groups),
            available_groups=len(self.available),
        )
        temp = self.state_dir / "health.json.new"
        temp.write_text(json.dumps(value), encoding="utf-8")
        temp.replace(self.state_dir / "health.json")

    async def check_ready(self):
        status = await self.api("/status")
        if not isinstance(status, dict) or status.get("status") != "已登录":
            self.available.clear()
            raise RuntimeError("wechat_login_required")
        listeners = await self.api("/listen")
        if not isinstance(listeners, list):
            raise RuntimeError("invalid_listener_response")
        ready = set()
        for group in self.settings.groups:
            if group in listeners:
                ready.add(group)
                continue
            try:
                reply = await self.api("/listen", {"who": group})
                if isinstance(reply, dict) and reply.get("success") is True:
                    ready.add(group)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("[mimicwx] 一个配置会话暂不可用，稍后重试；其他会话继续工作")
        self.available = ready
        if not ready:
            raise RuntimeError("no_configured_listener_available")

    def convert_message(self, group, raw):
        if group not in self.settings.groups:
            return None
        n = normalize(
            group,
            raw,
            self.settings.self_name,
            self.settings.mention_names,
            self.settings.unknown_sender_policy,
        )
        if (
            not n
            or self.ledger.is_echo(group, n["original_text"])
            or not self.ledger.claim(n["message_id"])
        ):
            return None
        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.self_id = self.self_id
        abm.session_id = n["group_id"]
        abm.group = Group(group_id=n["group_id"], group_name=group)
        abm.message_id = n["message_id"]
        abm.sender = MessageMember(user_id=n["sender_id"], nickname=n["sender_name"])
        abm.message = [At(qq=self.self_id, name=self.settings.self_name)] if n["mentioned"] else []
        if n["text"]:
            abm.message.append(Plain(n["text"]))
        abm.message_str = n["text"]
        abm.raw_message = dict(raw, _mimicwx_sender_known=n["sender_known"])
        event = MimicWXEvent(abm.message_str, abm, self.meta(), abm.session_id, self)
        event.set_extra("_disable_personal_memory", not n["sender_known"])
        event.set_extra("_mimicwx_sender_known", n["sender_known"])
        self.counts["received"] += 1
        self.counts["anonymous"] += int(not n["sender_known"])
        return event

    async def poll_once(self):
        pending = await self.api("/listen/messages")
        if not isinstance(pending, dict):
            raise RuntimeError("invalid_pending_messages")
        discard = not self.bootstrapped and self.settings.discard_startup_backlog
        for group in self.settings.groups:
            items = pending.get(group, [])
            if group not in self.available or not isinstance(items, list):
                continue
            for raw in items:
                if discard:
                    mid = identity(group, raw) if isinstance(raw, dict) else None
                    if mid:
                        self.ledger.claim(mid)
                else:
                    event = self.convert_message(group, raw)
                    if event:
                        # Await queue capacity instead of dropping an already claimed event.
                        await self._event_queue.put(event)
        self.bootstrapped = True
        self.ledger.prune()

    async def run(self):
        last_check = 0.0
        while not self.shutdown_event.is_set():
            try:
                if time.monotonic() - last_check > 30:
                    await self.check_ready()
                    last_check = time.monotonic()
                await self.poll_once()
                self.write_health(
                    "running" if len(self.available) == len(self.groups) else "degraded"
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if self.terminated:
                    break
                self.counts["errors"] += 1
                self.write_health("waiting_transport")
                logger.warning(
                    "[mimicwx] 通道暂不可用：%s；不输出响应正文、凭据或群消息", type(error).__name__
                )
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=self.settings.poll_interval
                )
            except asyncio.TimeoutError:
                pass

    @staticmethod
    async def image_bytes(component):
        source = str(component.file or component.url or "")
        parsed = urlsplit(source)
        if parsed.scheme.lower() in {"http", "https"} or source.startswith("//"):
            raise ValueError("remote_image_fetching_disabled_download_with_a_trusted_plugin_first")
        if source.startswith(("base64://", "data:image/")):
            if len(source) > MAX_INPUT_BYTES * 4 // 3 + 128:
                raise ValueError("image_input_size_exceeded")
        elif parsed.scheme in {"", "file"}:
            if parsed.scheme == "file" and parsed.netloc not in {"", "localhost"}:
                raise ValueError("remote_file_source_disabled")
            path = Path(unquote(parsed.path) if parsed.scheme == "file" else source)
            try:
                if path.stat().st_size > MAX_INPUT_BYTES:
                    raise ValueError("image_input_size_exceeded")
            except OSError:
                raise ValueError("local_image_unavailable") from None
        else:
            raise ValueError("unsupported_image_source")
        encoded = await component.convert_to_base64()
        if len(encoded) > MAX_INPUT_BYTES * 4 // 3 + 4:
            raise ValueError("image_input_size_exceeded")
        return base64.b64decode(encoded, validate=True)

    async def send_chain(self, gid, message):
        if self.terminated or gid not in self.groups:
            raise ValueError("adapter_stopped_or_chat_not_authorized")
        group = self.groups[gid]
        actions, text_parts = [], []

        def flush():
            text = "".join(text_parts).strip()
            if text:
                if len(text) > 5900:
                    raise ValueError("text_too_long")
                actions.append(("text", text))
            text_parts.clear()

        for component in message.chain:
            if isinstance(component, Plain):
                text_parts.append(component.text)
            elif isinstance(component, Image):
                flush()
                binary = await self.image_bytes(component)
                async with self.image_lock:
                    binary, ext = await asyncio.to_thread(prepare_image, binary)
                actions.append(
                    (
                        "image",
                        {
                            "file": base64.b64encode(binary).decode("ascii"),
                            "name": "astrbot." + ext,
                        },
                    )
                )
            elif isinstance(component, Reply):
                continue  # No reliable native WeChat quote mapping in this UI transport.
            elif isinstance(component, At):
                if component.name:
                    text_parts.append(component.name + "，")  # Plain text; not a native @.
            else:
                raise ValueError("unsupported_message_component_" + type(component).__name__)
        flush()
        async with self.send_lock:
            if self.terminated:
                raise RuntimeError("adapter_stopped")
            for kind, content in actions:
                try:
                    if kind == "text":
                        self.ledger.remember(group, content)
                        reply = await self.api("/send", {"to": group, "text": content})
                    else:
                        reply = await self.api("/send_image", dict(content, to=group))
                    if not isinstance(reply, dict) or reply.get("sent") is not True:
                        raise RuntimeError("transport_send_failed")
                    if reply.get("verified") is not True:
                        self.counts["unverified_sends"] += 1
                        logger.warning("[mimicwx] 已执行发送但未获确认；不会自动重发")
                    self.counts["sent_" + kind] += 1
                except BaseException:
                    self.counts["errors"] += 1
                    raise
                finally:
                    self.write_health("stopped" if self.terminated else "running")

    async def send_by_session(self, session, message_chain):
        if session.message_type != MessageType.GROUP_MESSAGE:
            raise ValueError("only_group_sessions_are_supported")
        await self.send_chain(session.session_id, message_chain)
        await super().send_by_session(session, message_chain)

    async def terminate(self):
        if self.terminated:
            return
        self.terminated = True
        self.shutdown_event.set()
        if self.client:
            await self.client.close()
        self.write_health("stopped")
        self.ledger.close()
        self._active_origins.discard(self.origin)


@register(
    "astrbot_plugin_whalebridge",
    "JulyEnd404",
    "鲸桥 WhaleBridge：实验性 AstrBot 微信平台适配器",
    "0.1.0",
)
class WhaleBridgePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
