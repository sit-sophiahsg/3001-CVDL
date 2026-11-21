"""Image-composition helpers for the shopper and model views.

All overlays are built on a transparent RGBA layer and merged with
``Image.alpha_composite``, so masks stay see-through instead of opaque.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BOX_BLUE = (43, 127, 214, 255)          # #2B7FD6
BLEMISH_RED = (255, 45, 45, 140)        # 55% red
BLEMISH_EDGE = (255, 223, 61, 255)      # #FFDF3D


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def _blemish_layer(size: tuple[int, int], items: list[dict]) -> Image.Image:
    """RGBA layer: semi-transparent red fill plus a yellow outline per blemish mask."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for item in items:
        mask = np.asarray(item.get("blemish_mask", np.zeros((1, 1), bool)), dtype=bool)
        if not mask.any():
            continue
        x0, y0 = item["box"][:2]
        mask_img = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
        stroke = max(3, min(mask.shape) // 60)
        grown = mask_img.filter(ImageFilter.MaxFilter(stroke * 2 + 1))
        outline = Image.fromarray(
            ((np.asarray(grown) > 0) & ~mask).astype(np.uint8) * 255, mode="L"
        )
        patch = Image.new("RGBA", mask_img.size, (0, 0, 0, 0))
        patch.paste(Image.new("RGBA", mask_img.size, BLEMISH_RED), (0, 0), mask_img)
        patch.paste(Image.new("RGBA", mask_img.size, BLEMISH_EDGE), (0, 0), outline)
        layer.alpha_composite(patch, (int(x0), int(y0)))
    return layer


def compose(image: Image.Image, items: list[dict], boxes: bool = True,
            blemish: bool = True, cam: bool = False) -> Image.Image:
    """Photo with optional Grad-CAM, blemish-mask and detector-box overlays."""
    base = image.convert("RGBA")
    if cam:
        for item in items:
            x0, y0, x1, y1 = (int(v) for v in item["box"])
            region = base.crop((x0, y0, x1, y1))
            heat = item["gradcam"].convert("RGBA").resize(region.size)
            base.paste(Image.blend(region, heat, 0.5), (x0, y0))
    if blemish:
        base = Image.alpha_composite(base, _blemish_layer(base.size, items))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    tag_font = _font(max(16, base.size[1] // 30))
    note_font = _font(max(12, base.size[1] // 45))
    for index, item in enumerate(items, start=1):
        x0, y0, x1, y1 = (int(v) for v in item["box"])
        if cam:
            draw.text((x0 + 8, y1 - 8), "Grad-CAM placeholder", font=note_font, anchor="lb",
                      fill="white", stroke_width=2, stroke_fill="black")
        if boxes:
            draw.rectangle((x0, y0, x1, y1), outline=BOX_BLUE, width=4)
            tag = f"#{index}"
            left, top, right, bottom = draw.textbbox((0, 0), tag, font=tag_font)
            tw, th = right - left, bottom - top
            ty = max(0, y0 - th - 12)
            draw.rectangle((x0, ty, x0 + tw + 14, ty + th + 12), fill=BOX_BLUE)
            draw.text((x0 + 7 - left, ty + 6 - top), tag, font=tag_font, fill="white")
    return Image.alpha_composite(base, layer).convert("RGB")


def blemish_photo(image: Image.Image, items: list[dict]) -> Image.Image:
    """The shopper's photo with only the blemish mask drawn on it."""
    return compose(image, items, boxes=False, blemish=True, cam=False)


def item_crop(image: Image.Image, item: dict) -> Image.Image:
    return image.convert("RGB").crop(tuple(int(v) for v in item["box"]))


def square(image: Image.Image, side: int = 160) -> Image.Image:
    """Centre-crop to a square thumbnail."""
    image = image.convert("RGB")
    w, h = image.size
    edge = min(w, h)
    left, top = (w - edge) // 2, (h - edge) // 2
    return image.crop((left, top, left + edge, top + edge)).resize((side, side))


def forecast_frames(image: Image.Image, item: dict) -> list[tuple[str, int, Image.Image]]:
    """[(label, day, thumbnail)] for Today, +1, +3 and +7 days."""
    frames = [("Today", 0, square(item_crop(image, item)))]
    for day in (1, 3, 7):
        frame = item.get("forecasts", {}).get(day)
        if frame is not None:
            frames.append((f"+{day} day" + ("" if day == 1 else "s"), day, square(frame)))
    return frames


def data_uri(image: Image.Image, max_side: int = 640) -> str:
    """Inline JPEG data URI, downscaled so pages stay light."""
    image = image.convert("RGB")
    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
