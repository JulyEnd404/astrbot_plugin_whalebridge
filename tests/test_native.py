"""Run inside the pinned AstrBot image; all messages and network calls are synthetic."""

import asyncio
import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_core import png, raw, settings

try:
    import astrbot.api  # noqa: F401

    HAS_ASTRBOT = True
except ImportError:
    HAS_ASTRBOT = False

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_ASTRBOT, "native AstrBot environment required")
class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        name = "public_mimicwx_test"
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                name, ROOT / "main.py", submodule_search_locations=[str(ROOT)]
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        self.module = sys.modules[name]
        self.tmp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(
            self.module.StarTools, "get_data_dir", return_value=Path(self.tmp.name)
        )
        self.data_patch.start()
        self.adapter = self.module.MimicWXAdapter(settings(), {}, asyncio.Queue())
        self.actions = []

        async def api(path, body=None):
            self.actions.append((path, body))
            return {"sent": True, "verified": True}

        self.adapter.api = api

    async def asyncTearDown(self):
        await self.adapter.terminate()
        self.data_patch.stop()
        self.tmp.cleanup()

    async def test_native_event_mention_and_memory_flag(self):
        e = self.adapter.convert_message("机器人测试群", raw())
        self.assertEqual(e.get_platform_name(), "mimicwx")
        self.assertEqual(
            str(e.unified_msg_origin),
            "test-wechat:GroupMessage:" + self.module.group_id("机器人测试群"),
        )
        self.assertEqual(str(e.get_messages()[0].qq), str(e.get_self_id()))
        self.assertFalse(e.get_extra("_disable_personal_memory"))
        e = self.adapter.convert_message(
            "机器人测试群", raw(mid="ui:2", msg_type="sys", sender="SYS", children=[])
        )
        self.assertTrue(e.get_extra("_disable_personal_memory"))

    async def test_duplicate_echo_and_nonwhitelist_ignored(self):
        self.assertIsNotNone(self.adapter.convert_message("机器人测试群", raw()))
        self.assertIsNone(self.adapter.convert_message("机器人测试群", raw()))
        self.assertIsNone(self.adapter.convert_message("陌生测试群", raw()))
        self.adapter.ledger.remember("机器人测试群", "合成回复")
        self.assertIsNone(self.adapter.convert_message("机器人测试群", raw("合成回复", mid="ui:2")))

    async def test_text_image_order_and_type(self):
        m = self.module
        chain = m.MessageChain(
            [
                m.Plain("第一句"),
                m.Image.fromBase64(base64.b64encode(png()).decode()),
                m.Plain("第二句"),
            ]
        )
        await self.adapter.send_chain(m.group_id("机器人测试群"), chain)
        self.assertEqual([x[0] for x in self.actions], ["/send", "/send_image", "/send"])
        self.assertEqual(self.actions[1][1]["name"], "astrbot.png")

    async def test_remote_or_invalid_image_refuses_whole_chain_before_text_send(self):
        m = self.module
        for image in [
            m.Image.fromURL("http://127.0.0.1/private"),
            m.Image.fromBase64("bm90IGFuIGltYWdl"),
        ]:
            with self.assertRaises((ValueError, OSError)):
                await self.adapter.send_chain(
                    m.group_id("机器人测试群"), m.MessageChain([m.Plain("不应发送"), image])
                )
        self.assertEqual(self.actions, [])

    async def test_outbound_whitelist_and_session_type(self):
        m = self.module
        with self.assertRaises(ValueError):
            await self.adapter.send_chain(m.group_id("陌生群"), m.MessageChain([]))
        from types import SimpleNamespace

        with self.assertRaises(ValueError):
            await self.adapter.send_by_session(
                SimpleNamespace(
                    session_id=m.group_id("机器人测试群"), message_type=m.MessageType.FRIEND_MESSAGE
                ),
                m.MessageChain([]),
            )
        self.assertEqual(self.actions, [])

    async def test_uncertain_delivery_no_retry_and_echo_digest_before_send(self):
        m = self.module

        async def failed(path, body=None):
            self.assertTrue(self.adapter.ledger.is_echo("机器人测试群", body["text"]))
            self.actions.append(path)
            return {"sent": False, "verified": False}

        self.adapter.api = failed
        with self.assertRaises(RuntimeError):
            await self.adapter.send_chain(
                m.group_id("机器人测试群"), m.MessageChain([m.Plain("合成回复")])
            )
        self.assertEqual(self.actions, ["/send"])

    async def test_unverified_success_records_uncertainty(self):
        m = self.module

        async def unverified(path, body=None):
            self.actions.append(path)
            return {"sent": True, "verified": False}

        self.adapter.api = unverified
        await self.adapter.send_chain(
            m.group_id("机器人测试群"), m.MessageChain([m.Plain("合成回复")])
        )
        self.assertEqual(self.actions, ["/send"])
        self.assertEqual(self.adapter.counts["unverified_sends"], 1)

    async def test_startup_discard_then_deliver_new_only(self):
        async def api(path, body=None):
            return {
                "机器人测试群": [
                    raw(mid="ui:old") if not self.adapter.bootstrapped else raw(mid="ui:new")
                ]
            }

        self.adapter.api = api
        self.adapter.available = {"机器人测试群"}
        await self.adapter.poll_once()
        self.assertTrue(self.adapter._event_queue.empty())
        await self.adapter.poll_once()
        self.assertEqual(self.adapter._event_queue.qsize(), 1)
        await self.adapter.poll_once()
        self.assertEqual(self.adapter._event_queue.qsize(), 1)

    async def test_one_missing_room_does_not_block_available_room(self):
        self.adapter.settings = self.module.settings_from(
            settings(groups=["机器人测试群", "不存在的测试群"])
        )

        async def api(path, body=None):
            if path == "/status":
                return {"status": "已登录"}
            if path == "/listen" and body is None:
                return ["机器人测试群"]
            raise RuntimeError("synthetic_failure")

        self.adapter.api = api
        await self.adapter.check_ready()
        self.assertEqual(self.adapter.available, {"机器人测试群"})

    async def test_duplicate_origin_and_idempotent_shutdown(self):
        with self.assertRaises(ValueError):
            self.module.MimicWXAdapter(settings(id="other-instance"), {}, asyncio.Queue())
        await self.adapter.terminate()
        await self.adapter.terminate()
        with self.assertRaises(ValueError):
            await self.adapter.send_chain(
                self.module.group_id("机器人测试群"), self.module.MessageChain([])
            )

    async def test_http_header_redirect_and_response_limit(self):
        from aiohttp import web

        m = self.module
        seen = []

        async def status(request):
            seen.append(request.headers.get("Authorization"))
            return web.json_response({"status": "已登录"})

        async def redirect(request):
            raise web.HTTPFound("/status")

        async def large(request):
            return web.Response(body=b"x" * 256)

        app = web.Application()
        app.router.add_get("/status", status)
        app.router.add_get("/redirect", redirect)
        app.router.add_get("/large", large)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        from dataclasses import replace

        port = site._server.sockets[0].getsockname()[1]
        self.adapter.settings = replace(self.adapter.settings, api_url=f"http://127.0.0.1:{port}")
        native_api = m.MimicWXAdapter.api.__get__(self.adapter)
        try:
            self.assertEqual((await native_api("/status"))["status"], "已登录")
            self.assertEqual(seen, ["Bearer synthetic-test-token"])
            with self.assertRaises(RuntimeError):
                await native_api("/redirect")
            self.assertEqual(len(seen), 1)
            with patch.object(m, "MAX_RESPONSE_BYTES", 128), self.assertRaises(RuntimeError):
                await native_api("/large")
        finally:
            await runner.cleanup()
