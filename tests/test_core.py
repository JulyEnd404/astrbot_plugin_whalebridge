"""Synthetic input only: configuration, identity, persistence and image bounds."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import codec
import config
import media


def settings(**overrides):
    return (
        dict(
            id="test-wechat",
            risk_acknowledged=True,
            api_url="http://unused",
            api_token_env="",
            api_token="synthetic-test-token",
            groups=["机器人测试群"],
            self_name="小助手",
            mention_names=["小助手"],
        )
        | overrides
    )


def raw(text="@小助手\u2005你好", sender="合成群友甲", mid="ui:1", **kwargs):
    return (
        dict(
            msg_type="friend",
            role="list item",
            children=[{}],
            sender=sender,
            content=text,
            msg_id=mid,
            index=2,
        )
        | kwargs
    )


def png():
    out = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(out, format="PNG")
    return out.getvalue()


class ConfigTests(unittest.TestCase):
    def test_explicit_ack_required(self):
        for ack in [False, None, 1, "true"]:
            with self.assertRaises(ValueError):
                config.settings_from(settings(risk_acknowledged=ack))

    def test_environment_wins_without_silent_fallback_and_repr_hides_token(self):
        with patch.dict(os.environ, {"MIMICWX_SYNTHETIC": "synthetic-env-secret"}):
            s = config.settings_from(settings(api_token_env="MIMICWX_SYNTHETIC"))
            self.assertEqual(s.api_token, "synthetic-env-secret")
            self.assertNotIn(s.api_token, repr(s))
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            config.settings_from(settings(api_token_env="MIMICWX_SYNTHETIC"))

    def test_invalid_addresses_and_header_injection(self):
        for url in [
            "file:///tmp/test",
            "http://name:secret@host",
            "https://host/x",
            "http://host/?token=x",
            "http://host/#x",
            "http://host:99999",
            "http://host\r\nInjected: x",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                config.settings_from(settings(api_url=url))
        with self.assertRaises(ValueError):
            config.settings_from(settings(api_token="x\r\nInjected: y"))

    def test_invalid_groups_names_interval_policy(self):
        for overrides in [
            dict(groups=[]),
            dict(groups=["a", "a"]),
            dict(groups=["\n"]),
            dict(groups=["a"] * 31),
            dict(mention_names=[]),
            dict(poll_interval=0),
            dict(poll_interval=True),
            dict(poll_interval=float("nan")),
            dict(id="../bad"),
            dict(unknown_sender_policy="person"),
        ]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                config.settings_from(settings(**overrides))


class CodecTests(unittest.TestCase):
    def normalize(self, r, group="机器人测试群", policy="mention_only"):
        return codec.normalize(group, r, "小助手", ("小助手",), policy)

    def test_unicode_mentions_require_boundary(self):
        n = self.normalize(raw())
        self.assertTrue(n["mentioned"])
        self.assertEqual(n["text"], "你好")
        self.assertFalse(self.normalize(raw("@小助手甲 你好"))["mentioned"])

    def test_chat_and_sender_isolation(self):
        a, b, c = (
            self.normalize(raw()),
            self.normalize(raw(), group="第二测试群"),
            self.normalize(raw(sender="乙")),
        )
        self.assertNotEqual(a["sender_id"], b["sender_id"])
        self.assertNotEqual(a["sender_id"], c["sender_id"])
        self.assertNotEqual(a["message_id"], b["message_id"])

    def test_unknown_policies_do_not_invent_personal_identity(self):
        r = raw(sender="SYS", msg_type="sys", children=[])
        a, b = self.normalize(r), self.normalize(dict(r, msg_id="ui:2"))
        self.assertFalse(a["sender_known"])
        self.assertNotEqual(a["sender_id"], b["sender_id"])
        self.assertIsNone(self.normalize(dict(r, content="继续说")))
        self.assertIsNone(self.normalize(r, policy="drop"))
        self.assertEqual(
            self.normalize(r, policy="group")["sender_id"],
            self.normalize(dict(r, msg_id="ui:2"), policy="group")["sender_id"],
        )

    def test_self_system_media_invalid_ignored(self):
        for r in [
            None,
            [],
            raw(sender="小助手"),
            raw(msg_type="time"),
            raw(mid=""),
            raw("[图片]"),
            raw("动画表情"),
            raw(""),
            raw("x" * 6001),
        ]:
            self.assertIsNone(self.normalize(r))

    def test_stable_cursor_and_legacy_indices(self):
        self.assertEqual(codec.identity("a", raw()), codec.identity("a", raw(index=42)))
        self.assertNotEqual(
            codec.identity("a", raw(mid="legacy")), codec.identity("a", raw(mid="legacy", index=42))
        )

    def test_persistent_dedup_echo_expiry_and_no_plaintext(self):
        now = [1000.0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.sqlite3"
            ledger = codec.Ledger(path, clock=lambda: now[0])
            self.assertTrue(ledger.claim("synthetic-message-id"))
            ledger.remember("私人合成群名", "合成测试正文")
            ledger.close()
            ledger = codec.Ledger(path, clock=lambda: now[0])
            self.assertFalse(ledger.claim("synthetic-message-id"))
            self.assertTrue(ledger.is_echo("私人合成群名", "合成测试正文"))
            self.assertFalse(ledger.is_echo("其他群", "合成测试正文"))
            self.assertNotIn("私人合成群名".encode(), path.read_bytes())
            self.assertNotIn("合成测试正文".encode(), path.read_bytes())
            now[0] += 301
            self.assertFalse(ledger.is_echo("私人合成群名", "合成测试正文"))
            now[0] += 7 * 86400
            ledger.prune()
            self.assertTrue(ledger.claim("synthetic-message-id"))
            ledger.close()


class MediaTests(unittest.TestCase):
    def test_small_png_roundtrips(self):
        binary = png()
        self.assertEqual(media.prepare_image(binary), (binary, "png"))

    def test_animation_downsize_preserves_duration_and_body_budget(self):
        frames = [Image.new("RGB", (64, 64), color) for color in ["red", "green", "blue"]]
        out = io.BytesIO()
        frames[0].save(
            out,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[70, 110, 130],
            loop=2,
        )
        # Force recompression with valid trailing padding instead of an expensive fixture.
        with patch.object(media, "MAX_BYTES", 600):
            binary, ext = media.prepare_image(out.getvalue() + b"\0" * 1000)
        self.assertEqual(ext, "gif")
        with Image.open(io.BytesIO(binary)) as result:
            self.assertGreater(result.n_frames, 1)
            total = 0
            for index in range(result.n_frames):
                result.seek(index)
                total += result.info["duration"]
            self.assertEqual(total, 310)
            self.assertEqual(result.info["loop"], 2)
        self.assertLess(len(binary) * 4 // 3 + 2000, 2 * 1024 * 1024)

    def test_animation_subsampling_keeps_total_duration(self):
        frames = [Image.new("RGB", (16, 16), (i * 2, i, 255 - i)) for i in range(90)]
        out = io.BytesIO()
        frames[0].save(
            out, format="GIF", save_all=True, append_images=frames[1:], duration=50, loop=0
        )
        with patch.object(media, "MAX_BYTES", 10000):
            binary, ext = media.prepare_image(out.getvalue() + b"\0" * 20000)
        self.assertEqual(ext, "gif")
        with Image.open(io.BytesIO(binary)) as result:
            self.assertLess(result.n_frames, 90)
            total = 0
            for index in range(result.n_frames):
                result.seek(index)
                total += result.info["duration"]
            self.assertEqual(total, 4500)

    def test_invalid_formats_and_resource_limits(self):
        for binary in [b"", b"not an image", b"x" * (media.MAX_INPUT_BYTES + 1)]:
            with self.assertRaises((ValueError, OSError)):
                media.prepare_image(binary)
        out = io.BytesIO()
        Image.new("RGB", (4, 4)).save(out, format="BMP")
        with self.assertRaises(ValueError):
            media.prepare_image(out.getvalue())
        with patch.object(media, "MAX_PIXELS", 2), self.assertRaises(ValueError):
            media.prepare_image(png())
        with patch.object(media, "MAX_DECODED_PIXELS", 2), self.assertRaises(ValueError):
            media.prepare_image(png())


if __name__ == "__main__":
    unittest.main()
