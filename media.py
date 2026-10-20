"""Validate and resize local/inline images to fit the legacy 2 MiB JSON body limit."""

import io
import math

from PIL import Image

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_BYTES = 1_400_000
MAX_PIXELS = 16_000_000
MAX_FRAMES = 500
MAX_DECODED_PIXELS = 64_000_000


def prepare_image(binary: bytes) -> tuple[bytes, str]:
    if not binary or len(binary) > MAX_INPUT_BYTES:
        raise ValueError("image_input_size_exceeded")
    with Image.open(io.BytesIO(binary)) as original:
        if original.format not in {"PNG", "JPEG", "GIF"}:
            raise ValueError("only_png_jpeg_gif_are_supported")
        if original.width * original.height > MAX_PIXELS:
            raise ValueError("image_pixel_limit_exceeded")
        count = getattr(original, "n_frames", 1)
        if count > MAX_FRAMES or original.width * original.height * count > MAX_DECODED_PIXELS:
            raise ValueError("image_frame_limit_exceeded")
        ext = {"PNG": "png", "JPEG": "jpg", "GIF": "gif"}[original.format]
        # Validate all frames before handing the original bytes to the UI client.
        if len(binary) <= MAX_BYTES:
            for index in range(count):
                original.seek(index)
                original.load()
            return binary, ext
        animated = original.format == "GIF" and count > 1
        loop = original.info.get("loop", 0)
        for side, max_frames in [(256, 80), (192, 60), (128, 40)]:
            frames, durations = [], []
            step = max(1, math.ceil(count / max_frames))
            for index in range(count):
                original.seek(index)
                duration = max(10, int(original.info.get("duration", 100)))
                if index % step == 0:
                    frame = original.convert("RGBA")
                    frame.thumbnail((side, side), Image.Resampling.LANCZOS)
                    frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))
                    durations.append(duration)
                else:
                    durations[-1] += duration
            output = io.BytesIO()
            if animated:
                frames[0].save(
                    output,
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=loop,
                    disposal=2,
                    optimize=True,
                )
                ext = "gif"
            else:
                frames[0].convert("RGB").save(output, format="JPEG", quality=85, optimize=True)
                ext = "jpg"
            encoded = output.getvalue()
            if len(encoded) <= MAX_BYTES:
                return encoded, ext
    raise ValueError("image_cannot_fit_transport_limit")
