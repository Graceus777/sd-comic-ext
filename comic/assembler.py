"""
Comic page assembler.

Ported from assemble_comic.py — layout engine, text overlays, page assembly,
image finding, and PDF/CBZ export. Pure PIL code, no A1111 dependency.
"""
import os
import re
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from . import text_styles


# -- config -----------------------------------------------------------------

PANELS_PER_PAGE = 4
PAGE_WIDTH = 1200
PANEL_GAP = 12
PAGE_MARGIN = 16
BG_COLOR = (15, 15, 20)

SCRIPT_PAGE_WIDTH = 2400
SCRIPT_PANEL_GAP = 10
SCRIPT_PAGE_MARGIN = 20
SCRIPT_BG = (10, 10, 15)


# -- fonts ------------------------------------------------------------------

def get_font(size: int, bold: bool = False, family: str = "sans"):
    """Load a logical lettering font family, with a safe PIL fallback."""
    font_path = text_styles.resolve_font_path(family, bold=bold)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, ValueError):
            pass
    return ImageFont.load_default()


FONT_CAPTION = get_font(32, bold=False, family="serif")
FONT_DIALOGUE = get_font(30, bold=False, family="comic")
FONT_LABEL = get_font(22, bold=True, family="sans")

_font_cache: Dict = {}


def _scaled_font(base_size: int, panel_w: int, bold: bool = False,
                 family: str = "sans"):
    """Get a font scaled to panel width. Base sizes designed for ~1200px panels."""
    size = max(8, min(240, int(base_size * panel_w / 1200)))
    key = (size, bold, family)
    if key not in _font_cache:
        _font_cache[key] = get_font(size, bold, family)
    return _font_cache[key]


# -- drawing helpers --------------------------------------------------------

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    """Wrap text to a pixel width, including newlines and long sound words."""
    max_width = max(1, int(max_width))

    def width(value: str) -> int:
        bbox = draw.textbbox((0, 0), value, font=font)
        return bbox[2] - bbox[0]

    def split_long_word(word: str) -> List[str]:
        chunks: List[str] = []
        chunk = ""
        for char in word:
            candidate = chunk + char
            if chunk and width(candidate) > max_width:
                chunks.append(chunk)
                chunk = char
            else:
                chunk = candidate
        if chunk:
            chunks.append(chunk)
        return chunks or [word]

    lines: List[str] = []
    paragraphs = str(text).splitlines() or [""]
    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            pieces = split_long_word(word) if width(word) > max_width else [word]
            for piece in pieces:
                candidate = f"{current} {piece}".strip()
                if not current or width(candidate) <= max_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = piece
        if current:
            lines.append(current)
    return lines or [""]


# -- shape drawing ----------------------------------------------------------

def _draw_box_shape(odraw: ImageDraw.ImageDraw, box, spec: Dict):
    """Draw a bubble/box silhouette for the given style spec inside `box`."""
    x0, y0, x1, y1 = box
    fill = tuple(spec["fill"])
    outline = tuple(spec["outline"])
    ow = int(spec.get("outline_width", 0))
    radius = int(spec.get("radius", 0))
    shape = spec["shape"]

    if shape == "plain":
        return  # text-only (SFX); no silhouette

    if shape in ("rect",):
        odraw.rectangle([x0, y0, x1, y1], fill=fill,
                        outline=outline if ow else None, width=max(ow, 1))

    elif shape in ("rounded", "dashed"):
        odraw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                                outline=outline if ow else None, width=max(ow, 1))
        if shape == "dashed":
            # overlay a dashed border on top of the (already drawn) solid one
            odraw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                                    fill=fill, outline=None)
            _dashed_round_border(odraw, box, radius, outline, max(ow, 1))

    elif shape == "cloud":
        _draw_cloud(odraw, box, fill, outline, max(ow, 1))

    elif shape == "spiky":
        _draw_spiky(odraw, box, fill, outline, max(ow, 1))


def _dashed_round_border(odraw, box, radius, outline, width, dash=14, gap=10):
    """Draw dashed straight edges with connected rounded corners."""
    x0, y0, x1, y1 = box
    radius = max(width, radius)
    dash = max(4, min(dash, radius))
    gap = max(3, min(gap, radius))

    def dashed_line(p0, p1):
        import math
        x_a, y_a = p0
        x_b, y_b = p1
        length = math.hypot(x_b - x_a, y_b - y_a)
        if length == 0:
            return
        ux, uy = (x_b - x_a) / length, (y_b - y_a) / length
        d = 0.0
        while d < length:
            sx, sy = x_a + ux * d, y_a + uy * d
            e = min(d + dash, length)
            ex, ey = x_a + ux * e, y_a + uy * e
            odraw.line([sx, sy, ex, ey], fill=outline, width=width)
            d += dash + gap

    dashed_line((x0 + radius, y0), (x1 - radius, y0))
    dashed_line((x1, y0 + radius), (x1, y1 - radius))
    dashed_line((x1 - radius, y1), (x0 + radius, y1))
    dashed_line((x0, y1 - radius), (x0, y0 + radius))
    diameter = radius * 2
    odraw.arc((x0, y0, x0 + diameter, y0 + diameter), 180, 270, fill=outline, width=width)
    odraw.arc((x1 - diameter, y0, x1, y0 + diameter), 270, 360, fill=outline, width=width)
    odraw.arc((x1 - diameter, y1 - diameter, x1, y1), 0, 90, fill=outline, width=width)
    odraw.arc((x0, y1 - diameter, x0 + diameter, y1), 90, 180, fill=outline, width=width)


def _draw_cloud(odraw, box, fill, outline, ow):
    """Scalloped 'thought cloud' from overlapping bumps around a core.

    Drawn outline-first (a slightly larger silhouette in the outline colour),
    then the fill on top, so only the outer contour shows — no internal seams.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    bump = max(18, min(w, h) // 4)
    r = bump // 2
    centres = []
    nx = max(3, int(round(w / bump)))
    ny = max(2, int(round(h / bump)))
    for i in range(nx + 1):
        cx = x0 + i * w / nx
        centres.append((cx, y0)); centres.append((cx, y1))
    for j in range(1, ny):
        cy = y0 + j * h / ny
        centres.append((x0, cy)); centres.append((x1, cy))

    def silhouette(radius, col):
        for cx, cy in centres:
            odraw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=col)
        odraw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=col)

    if ow:
        silhouette(r + ow, outline)   # outline layer (slightly larger)
    silhouette(r, fill)               # fill layer on top hides inner seams


def _draw_spiky(odraw, box, fill, outline, ow):
    """Jagged 'shout' burst as a star polygon around the box ellipse."""
    import math
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    spikes = max(12, int((x1 - x0) / 34))

    def burst(scale):
        pts = []
        for k in range(spikes * 2):
            ang = math.pi * k / spikes
            rad = scale if k % 2 == 0 else scale * 0.74
            pts.append((cx + math.cos(ang) * rx * rad,
                        cy + math.sin(ang) * ry * rad))
        return pts

    if ow:
        odraw.polygon(burst(1.06), fill=outline)  # outline layer
    odraw.polygon(burst(1.0), fill=fill)          # fill layer on top


def _draw_tail(odraw, box, spec: Dict, anchor: str):
    """Draw a scale-aware tail pointing from the bubble into the panel."""
    x0, y0, x1, y1 = box
    kind = spec.get("tail", "none")
    if kind == "none":
        return
    fill = tuple(spec["fill"])
    outline = tuple(spec["outline"])
    ow = max(int(spec.get("outline_width", 0)), 1)
    scale = max(0.35, _as_float(spec.get("_scale"), 1))
    tail_len = max(8, int(round(22 * scale)))
    base_w = max(9, int(round(26 * scale)))
    inset = max(3, int(round(4 * scale)))
    if anchor.startswith("top"):
        base_y, direction = y1, 1
    elif anchor.startswith("bottom"):
        base_y, direction = y0, -1
    else:
        base_y, direction = y1, 1
    tip_y = base_y + tail_len * direction
    cx = x0 + (x1 - x0) * (0.7 if "right" in anchor else 0.28)

    if kind == "triangle":
        pts = [(cx, base_y), (cx + base_w, base_y), (cx + inset, tip_y)]
        odraw.polygon(pts, fill=fill, outline=outline)
        odraw.line([(cx, base_y), (cx + base_w, base_y)], fill=fill, width=ow + 1)
    elif kind == "jagged":
        mid = max(4, int(round(10 * scale)))
        pts = [
            (cx, base_y), (cx + base_w, base_y),
            (cx + int(base_w * 0.7), tip_y),
            (cx + int(base_w * 0.35), base_y + mid * direction),
            (cx, tip_y),
        ]
        odraw.polygon(pts, fill=fill, outline=outline)
    elif kind == "dots":
        step = max(7, int(round(18 * scale))) * direction
        radius = max(3, int(round(9 * scale)))
        dy = base_y + step
        for shrink in (radius, max(2, int(radius * 0.7)), max(1, int(radius * 0.45))):
            odraw.ellipse(
                [cx - shrink, dy - shrink, cx + shrink, dy + shrink],
                fill=fill, outline=outline, width=ow,
            )
            dy += step
            cx += max(2, int(round(6 * scale)))


# -- text element engine ----------------------------------------------------

REF_PANEL_W = 1200  # font/padding sizes are authored against a 1200px panel


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _parse_color(value, fallback):
    """Accept #RGB/#RRGGBB or an RGB(A) sequence; otherwise use fallback."""
    if isinstance(value, str):
        raw = value.strip().lstrip("#")
        if len(raw) == 3 and all(char in "0123456789abcdefABCDEF" for char in raw):
            raw = "".join(char * 2 for char in raw)
        if len(raw) == 6 and all(char in "0123456789abcdefABCDEF" for char in raw):
            return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            rgb = tuple(max(0, min(255, int(channel))) for channel in value[:3])
            if len(value) >= 4:
                return rgb + (max(0, min(255, int(value[3]))),)
            return rgb
        except (TypeError, ValueError):
            pass
    return tuple(fallback)


def draw_text_element(panel: Image.Image, text: str, spec: Dict, *,
                      anchor: str, offset=(0, 0), width_frac: float = 0.7,
                      font_px: int = 30, font_family: str = "sans",
                      rotation: float = 0):
    """Render one styled, positioned lettering layer onto ``panel``.

    Sizes are authored at a 1200px reference width. Rotation is clockwise.
    The image is modified in place and may be RGB or RGBA.
    """
    if not text or not str(text).strip():
        return
    pw, ph = panel.size
    raw = str(text)
    if spec.get("all_caps"):
        raw = raw.upper()

    scale = pw / REF_PANEL_W
    render_spec = dict(spec)
    render_spec["_scale"] = scale
    for key in ("radius", "outline_width", "text_stroke"):
        authored = max(0, int(_as_float(render_spec.get(key, 0), 0)))
        render_spec[key] = max(1, int(round(authored * scale))) if authored else 0

    font_px = int(max(8, min(240, _as_float(font_px, 30))))
    font = _scaled_font(
        font_px, pw, bold=bool(render_spec.get("bold", False)),
        family=font_family or render_spec.get("font_family", "sans"),
    )
    padding = max(4, int(_as_float(render_spec.get("padding", 16), 16) * scale))
    try:
        font_height = font.size
    except AttributeError:
        bbox = ImageDraw.Draw(panel).textbbox((0, 0), "Ag", font=font)
        font_height = max(8, bbox[3] - bbox[1])
    line_h = max(1, int(font_height * 1.25))

    width_frac = max(0.15, min(1.0, _as_float(width_frac, 0.7)))
    full_width = width_frac >= 0.98
    box_w = pw if full_width else int(width_frac * pw)

    shape = render_spec.get("shape", "rounded")
    tmp = ImageDraw.Draw(panel)
    inner = max(1, box_w - padding * 2)
    if shape == "plain":
        wrap_w = box_w
    elif shape in ("cloud", "spiky"):
        wrap_w = max(1, int(inner * 0.78))
    else:
        wrap_w = inner
    lines = wrap_text(raw, font, wrap_w, tmp)
    text_h = line_h * len(lines)
    box_h = text_h + padding * 2
    if shape in ("cloud", "spiky"):
        box_h = max(box_h, int(box_w * 0.42))

    pad_shape = 0
    if shape == "cloud":
        pad_shape = int(min(box_w, box_h) // 5)
    elif shape == "spiky":
        pad_shape = int(box_w * 0.12)
    slot_w = box_w + pad_shape * 2
    slot_h = box_h + pad_shape * 2

    anchor = text_styles.normalize_anchor(
        anchor, render_spec.get("default_anchor", "bottom-center")
    )
    margin = 0 if full_width else max(8, int(20 * scale))
    parts = anchor.split("-")
    vert, horiz = (parts[0], parts[1]) if len(parts) == 2 else ("center", "center")

    if horiz == "left":
        x = margin
    elif horiz == "right":
        x = pw - slot_w - margin
    else:
        x = (pw - slot_w) // 2
    if vert == "top":
        y = margin
    elif vert == "bottom":
        y = ph - slot_h - margin
    else:
        y = (ph - slot_h) // 2

    if not isinstance(offset, (list, tuple)) or len(offset) != 2:
        offset = (0, 0)
    x += int(_as_float(offset[0], 0) / 100.0 * pw)
    y += int(_as_float(offset[1], 0) / 100.0 * ph)
    x = max(-pad_shape, min(x, pw - slot_w + pad_shape))
    y = max(-pad_shape, min(y, ph - slot_h + pad_shape))

    box = (
        int(x + pad_shape), int(y + pad_shape),
        int(x + pad_shape + box_w), int(y + pad_shape + box_h),
    )

    layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _draw_box_shape(draw, box, render_spec)
    _draw_tail(draw, box, render_spec, anchor)

    tfill = tuple(render_spec.get("text_fill", (15, 15, 15)))
    stroke = int(render_spec.get("text_stroke", 0))
    stroke_fill = tuple(render_spec.get("text_stroke_fill", (0, 0, 0)))
    centred = shape in ("cloud", "spiky", "plain")
    tx = box[0] + padding
    ty = box[1] + ((box_h - text_h) // 2 if centred else padding)
    for line in lines:
        if centred:
            line_box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
            line_w = line_box[2] - line_box[0]
            lx = box[0] + (box_w - line_w) // 2
        else:
            lx = tx
        draw.text(
            (lx, ty), line, fill=tfill, font=font,
            stroke_width=stroke, stroke_fill=stroke_fill,
        )
        ty += line_h

    angle = max(-45.0, min(45.0, _as_float(rotation, 0)))
    if angle:
        centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        layer = layer.rotate(-angle, resample=Image.BICUBIC, center=centre)

    base = panel if panel.mode == "RGBA" else panel.convert("RGBA")
    base.alpha_composite(layer)
    if base is not panel:
        panel.paste(base.convert(panel.mode))


def _resolve_and_draw(panel: Image.Image, data: Dict, key: str):
    """Resolve a legacy caption/dialogue field and render it safely."""
    text = data.get(key, "")
    if not text or not str(text).strip() or str(text).strip() == "...":
        return
    default_style = (
        text_styles.CAPTION_DEFAULT if key == "caption"
        else text_styles.DIALOGUE_DEFAULT
    )
    spec = text_styles.get_style(data.get(f"{key}_style"), fallback=default_style)
    spec["text_fill"] = _parse_color(
        data.get(f"{key}_color"), spec.get("text_fill", (15, 15, 15))
    )
    spec["text_stroke_fill"] = _parse_color(
        data.get(f"{key}_outline_color"), spec.get("text_stroke_fill", (0, 0, 0))
    )
    anchor = data.get(f"{key}_anchor") or spec["default_anchor"]

    width = data.get(f"{key}_width")
    if width in (None, "", 0):
        width_frac = spec["default_width"]
    else:
        width_value = _as_float(width, spec["default_width"])
        width_frac = width_value / 100.0 if width_value > 1.5 else width_value

    offset = data.get(f"{key}_offset") or (0, 0)
    font_px = data.get(f"{key}_font_size") or spec["default_font"]
    font_family = data.get(f"{key}_font") or spec.get("font_family", "sans")
    rotation = data.get(f"{key}_rotation", spec.get("default_rotation", 0))

    draw_text_element(
        panel, text, spec, anchor=anchor, offset=offset,
        width_frac=width_frac, font_px=int(_as_float(font_px, spec["default_font"])),
        font_family=font_family, rotation=rotation,
    )


def _draw_extra_lettering(panel: Image.Image, element: Dict):
    """Render one item from a panel's independent ``lettering`` list."""
    if not isinstance(element, dict):
        return
    text = element.get("text", "")
    if not text or not str(text).strip():
        return
    spec = text_styles.get_style(element.get("style"), text_styles.EFFECT_DEFAULT)
    spec["text_fill"] = _parse_color(
        element.get("color"), spec.get("text_fill", (15, 15, 15))
    )
    spec["text_stroke_fill"] = _parse_color(
        element.get("outline_color"), spec.get("text_stroke_fill", (0, 0, 0))
    )
    width = _as_float(element.get("width"), spec["default_width"])
    width_frac = width / 100.0 if width > 1.5 else width
    draw_text_element(
        panel, text, spec,
        anchor=element.get("anchor") or spec["default_anchor"],
        offset=element.get("offset") or (0, 0),
        width_frac=width_frac,
        font_px=int(_as_float(element.get("font_size"), spec["default_font"])),
        font_family=element.get("font") or spec.get("font_family", "sans"),
        rotation=element.get("rotation", spec.get("default_rotation", 0)),
    )


def render_panel_lettering(panel: Image.Image, data: Dict):
    """Render caption, dialogue, then any number of independent extra layers."""
    _resolve_and_draw(panel, data, "caption")
    _resolve_and_draw(panel, data, "dialogue")
    lettering = data.get("lettering", [])
    if isinstance(lettering, list):
        for element in lettering:
            _draw_extra_lettering(panel, element)


# -- legacy wrappers (kept for callers that pass plain text) ----------------

def draw_caption_overlay(panel: Image.Image, text: str, font=None):
    """Backward-compatible default narration bar."""
    _resolve_and_draw(panel, {"caption": text}, "caption")


def draw_dialogue_overlay(panel: Image.Image, text: str, font=None):
    """Backward-compatible default speech bubble."""
    _resolve_and_draw(panel, {"dialogue": text}, "dialogue")

# -- image fitting ----------------------------------------------------------

def fit_image_to_slot(img: Image.Image, slot_w: int, slot_h: int) -> Image.Image:
    """Scale image to cover slot, center-crop to exact dimensions."""
    img = img.convert("RGBA")
    iw, ih = img.size
    scale = max(slot_w / iw, slot_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - slot_w) // 2
    top = (new_h - slot_h) // 2
    return img.crop((left, top, left + slot_w, top + slot_h))


# -- layout engine ----------------------------------------------------------

def _layout_splash(W, gap):
    h = int(W * 1.3)
    return [(0, 0, W, h)], h


def _layout_two_row(W, gap):
    rh = int(W * 1.1)
    return [
        (0, 0, W, rh),
        (0, rh + gap, W, rh),
    ], rh * 2 + gap


def _layout_three_row(W, gap):
    pw = (W - gap * 2) // 3
    h = int(pw * 1.25)
    return [
        (0, 0, pw, h),
        (pw + gap, 0, pw, h),
        ((pw + gap) * 2, 0, pw, h),
    ], h


def _layout_L_right(W, gap):
    w_big = (W - gap) * 2 // 3
    w_sm = W - gap - w_big
    h_total = int(w_big * 1.25)
    h_sm = (h_total - gap) // 2
    return [
        (0, 0, w_big, h_total),
        (w_big + gap, 0, w_sm, h_sm),
        (w_big + gap, h_sm + gap, w_sm, h_sm),
    ], h_total


def _layout_L_left(W, gap):
    w_sm = (W - gap) // 3
    w_big = W - gap - w_sm
    h_total = int(w_big * 1.25)
    h_sm = (h_total - gap) // 2
    return [
        (0, 0, w_sm, h_sm),
        (0, h_sm + gap, w_sm, h_sm),
        (w_sm + gap, 0, w_big, h_total),
    ], h_total


def _layout_T_top(W, gap, n_bottom=3):
    h_top = int(W * 0.6)
    pw = (W - gap * (n_bottom - 1)) // n_bottom
    h_bot = int(pw * 1.25)
    slots = [(0, 0, W, h_top)]
    for i in range(n_bottom):
        x = i * (pw + gap)
        slots.append((x, h_top + gap, pw, h_bot))
    return slots, h_top + gap + h_bot


def _layout_T_bottom(W, gap, n_top=3):
    pw = (W - gap * (n_top - 1)) // n_top
    h_top = int(pw * 1.25)
    h_bot = int(W * 0.6)
    slots = []
    for i in range(n_top):
        x = i * (pw + gap)
        slots.append((x, 0, pw, h_top))
    slots.append((0, h_top + gap, W, h_bot))
    return slots, h_top + gap + h_bot


def _layout_strip(W, gap, n=3):
    pw = (W - gap * (n - 1)) // n
    h = int(pw * 1.25)
    slots = [(i * (pw + gap), 0, pw, h) for i in range(n)]
    return slots, h


def _layout_grid_2x2(W, gap):
    pw = (W - gap) // 2
    h = int(pw * 1.25)
    return [
        (0, 0, pw, h),
        (pw + gap, 0, pw, h),
        (0, h + gap, pw, h),
        (pw + gap, h + gap, pw, h),
    ], h * 2 + gap


def _layout_wide_focus(W, gap):
    h = int(W * 1.0)
    return [(0, 0, W, h)], h


def _layout_tall_split(W, gap):
    pw = (W - gap) // 2
    h = int(pw * 1.6)
    return [
        (0, 0, pw, h),
        (pw + gap, 0, pw, h),
    ], h


def _layout_staircase(W, gap):
    pw = int(W * 0.55)
    h = int(pw * 1.25)
    step_x = (W - pw) // 2
    return [
        (0, 0, pw, h),
        (step_x, h + gap, pw, h),
        (step_x * 2, (h + gap) * 2, pw, h),
    ], h * 3 + gap * 2


def compute_layout(layout_type: str, usable_w: int, gap: int,
                   n_panels: int) -> Tuple[List[Tuple[int, int, int, int]], int]:
    """
    Compute panel slot positions for a page layout.
    Returns (slots, total_height) where each slot is (x, y, w, h).
    """
    lt = layout_type.lower().replace("-", "_")

    if lt == "splash":
        return _layout_splash(usable_w, gap)
    elif lt == "two_row":
        return _layout_two_row(usable_w, gap)
    elif lt == "three_row":
        return _layout_three_row(usable_w, gap)
    elif lt == "l_right":
        return _layout_L_right(usable_w, gap)
    elif lt == "l_left":
        return _layout_L_left(usable_w, gap)
    elif lt == "t_top":
        n_bottom = n_panels - 1
        return _layout_T_top(usable_w, gap, n_bottom=max(2, n_bottom))
    elif lt == "t_bottom":
        n_top = n_panels - 1
        return _layout_T_bottom(usable_w, gap, n_top=max(2, n_top))
    elif lt == "strip":
        return _layout_strip(usable_w, gap, n=n_panels)
    elif lt == "grid_2x2":
        return _layout_grid_2x2(usable_w, gap)
    elif lt == "wide_focus":
        return _layout_wide_focus(usable_w, gap)
    elif lt == "tall_split":
        return _layout_tall_split(usable_w, gap)
    elif lt == "staircase":
        return _layout_staircase(usable_w, gap)
    else:
        # fallback: vertical stack
        rh = int(usable_w * 0.55)
        slots = [(0, i * (rh + gap), usable_w, rh) for i in range(n_panels)]
        return slots, n_panels * rh + (n_panels - 1) * gap


# -- template parser (storyboard mode) -------------------------------------

def parse_template(path: str) -> Tuple[Dict, List[Dict]]:
    """Parse storyboard template. Returns (header, frames)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    parts = re.split(r"^-{3,}\s*$", text, flags=re.MULTILINE)
    header_text = parts[0] if parts else ""
    frame_texts = parts[1:] if len(parts) > 1 else []

    header = {}
    for line in header_text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            m = re.match(r"^#\s(\w[\w_]*)\s*:\s*(.+)$", line)
            if m:
                header[m.group(1).lower()] = m.group(2).strip()

    frames = []
    for ft in frame_texts:
        kv = {}
        for line in ft.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
            if m:
                kv[m.group(1).lower()] = m.group(2).strip()
        if kv:
            frames.append(kv)

    return header, frames


# -- image finders ----------------------------------------------------------

def find_panel_images(image_dir: str, template_title: str, char_name: str,
                      num_frames: int) -> List[Optional[str]]:
    """Find generated images matching template+character+frame pattern."""
    tpl_tag = re.sub(r"[^\w]", "_", template_title)[:15]
    char_tag = char_name.replace(" ", "_")[:25]
    prefix = f"{tpl_tag}_{char_tag}"

    all_files = {}
    if os.path.isdir(image_dir):
        for fname in sorted(os.listdir(image_dir)):
            if not fname.lower().endswith(".png"):
                continue
            if prefix.lower() in fname.lower():
                m = re.search(r"_f(\d+)", fname)
                if m:
                    fnum = int(m.group(1))
                    if fnum not in all_files:
                        all_files[fnum] = os.path.join(image_dir, fname)

    return [all_files.get(i) for i in range(1, num_frames + 1)]


def find_script_panel_image(panel: Dict, image_dirs: List[str],
                            script_tag: str) -> Optional[str]:
    """
    Find the image for a comic script panel.
    Priority: explicit reuse path > generated image matching panel ID.
    """
    # 1. Explicit reuse
    reuse = panel.get("reuse")
    if reuse:
        for d in image_dirs:
            p = os.path.join(d, reuse)
            if os.path.isfile(p):
                return p
        if os.path.isfile(reuse):
            return reuse

    # 2. Match by script_tag + panel ID pattern
    panel_id = panel.get("id", "")
    if panel_id:
        tag_lower = script_tag.lower()
        pid_lower = panel_id.lower()
        for d in image_dirs:
            if not os.path.isdir(d):
                continue
            matches_no_suffix = []
            matches_2 = []
            matches_1 = []
            for fname in sorted(os.listdir(d), reverse=True):
                fl = fname.lower()
                if not fl.endswith(".png"):
                    continue
                if fl.endswith(("_bg.png", "_char.png", "_mask.png")):
                    continue
                if tag_lower in fl and pid_lower in fl:
                    if "_1.png" in fl:
                        matches_1.append(fname)
                    elif "_2.png" in fl:
                        matches_2.append(fname)
                    else:
                        matches_no_suffix.append(fname)
            for group in (matches_no_suffix, matches_2, matches_1):
                if group:
                    return os.path.join(d, group[0])

    return None


# -- panel builders ---------------------------------------------------------

def build_panel(img_path: Optional[str], frame: Dict, panel_w: int) -> Image.Image:
    """Load image, scale to panel_w, overlay caption and dialogue. Returns RGBA."""
    if img_path and os.path.isfile(img_path):
        im = Image.open(img_path).convert("RGBA")
        scale = panel_w / im.width
        new_h = int(im.height * scale)
        im = im.resize((panel_w, new_h), Image.LANCZOS)
    else:
        new_h = int(panel_w * 1.25)
        im = Image.new("RGBA", (panel_w, new_h), (40, 40, 50, 255))
        d = ImageDraw.Draw(im)
        d.text((panel_w // 4, new_h // 2), "[ missing ]",
               fill=(100, 100, 100), font=FONT_LABEL)

    render_panel_lettering(im, frame)

    return im


def build_script_panel(img_path: Optional[str], panel: Dict,
                       slot_w: int, slot_h: int) -> Image.Image:
    """Build a panel from a comic script entry, fitted to slot dimensions."""
    if img_path and os.path.isfile(img_path):
        im = Image.open(img_path).convert("RGBA")
        im = fit_image_to_slot(im, slot_w, slot_h)
    else:
        im = Image.new("RGBA", (slot_w, slot_h), (40, 40, 50, 255))
        d = ImageDraw.Draw(im)
        label = panel.get("id", "???")
        lbl_font = _scaled_font(22, slot_w, bold=True)
        d.text((slot_w // 4, slot_h // 2), f"[ {label} missing ]",
               fill=(100, 100, 100), font=lbl_font)

    render_panel_lettering(im, panel)

    return im


# -- page assembly ----------------------------------------------------------

def assemble_page(panels: List[Tuple[Optional[str], Dict]],
                  page_num: int, page_width: int = PAGE_WIDTH) -> Image.Image:
    """Single-column comic page. Each panel is full-width with text overlaid."""
    panel_w = page_width - PAGE_MARGIN * 2

    built = []
    for img_path, frame in panels:
        panel_img = build_panel(img_path, frame, panel_w)
        built.append(panel_img)

    total_h = PAGE_MARGIN * 2 + sum(p.height for p in built) + PANEL_GAP * (len(built) - 1)
    page = Image.new("RGBA", (page_width, total_h), BG_COLOR + (255,))
    draw = ImageDraw.Draw(page)

    y = PAGE_MARGIN
    for panel_img in built:
        page.paste(panel_img, (PAGE_MARGIN, y))
        draw.rectangle(
            [(PAGE_MARGIN - 1, y - 1),
             (PAGE_MARGIN + panel_img.width, y + panel_img.height)],
            outline=(255, 255, 255, 120), width=2
        )
        y += panel_img.height + PANEL_GAP

    return page


def assemble_grid_page(panels: List[Tuple[Optional[str], Dict]],
                       cols: int = 3, page_width: int = 3600) -> Image.Image:
    """Grid layout: all panels on one page, multiple per row."""
    gap = PANEL_GAP
    margin = PAGE_MARGIN
    usable_w = page_width - margin * 2
    panel_w = (usable_w - gap * (cols - 1)) // cols

    built = []
    for img_path, frame in panels:
        panel_img = build_panel(img_path, frame, panel_w)
        built.append(panel_img)

    rows = []
    for i in range(0, len(built), cols):
        rows.append(built[i:i + cols])

    row_heights = [max(p.height for p in row) for row in rows]

    total_h = margin * 2 + sum(row_heights) + gap * (len(rows) - 1)
    page = Image.new("RGBA", (page_width, total_h), BG_COLOR + (255,))
    draw = ImageDraw.Draw(page)

    y = margin
    for ri, row in enumerate(rows):
        x = margin
        for panel_img in row:
            page.paste(panel_img, (x, y))
            draw.rectangle(
                [(x - 1, y - 1), (x + panel_img.width, y + panel_img.height)],
                outline=(255, 255, 255, 120), width=2
            )
            x += panel_w + gap
        y += row_heights[ri] + gap

    return page


def assemble_scripted_page(page_def: Dict, image_dirs: List[str],
                           script_tag: str,
                           page_width: int = SCRIPT_PAGE_WIDTH) -> Image.Image:
    """Assemble one comic page from a script page definition."""
    margin = SCRIPT_PAGE_MARGIN
    gap = SCRIPT_PANEL_GAP
    usable_w = page_width - margin * 2

    panels = page_def.get("panels", [])
    layout_type = page_def.get("layout", "two_row")
    n = len(panels)

    if n == 0:
        return Image.new("RGBA", (page_width, 100), SCRIPT_BG + (255,))

    slots, content_h = compute_layout(layout_type, usable_w, gap, n)

    use_count = min(n, len(slots))

    total_h = content_h + margin * 2
    page = Image.new("RGBA", (page_width, total_h), SCRIPT_BG + (255,))
    draw = ImageDraw.Draw(page)

    for i in range(use_count):
        panel = panels[i]
        sx, sy, sw, sh = slots[i]

        img_path = find_script_panel_image(panel, image_dirs, script_tag)
        panel_img = build_script_panel(img_path, panel, sw, sh)

        px, py = margin + sx, margin + sy
        page.paste(panel_img, (px, py))

        draw.rectangle(
            [(px - 1, py - 1), (px + sw, py + sh)],
            outline=(255, 255, 255, 140), width=2
        )

    return page


# -- full pipelines ---------------------------------------------------------

def assemble_comic(template_path: str, image_dir: str, char_name: str,
                   output_dir: str, panels_per_page: int = PANELS_PER_PAGE,
                   single_page: bool = False, grid_cols: int = 3,
                   grid_width: int = 3600) -> List[str]:
    """Full storyboard pipeline: find images, build pages, save."""
    header, frames = parse_template(template_path)
    title = header.get("title", Path(template_path).stem)

    images = find_panel_images(image_dir, title, char_name, len(frames))
    found = sum(1 for x in images if x is not None)

    if found == 0:
        return []

    os.makedirs(output_dir, exist_ok=True)

    comic_tag = re.sub(r"[^\w]", "_", title)[:20]
    char_tag = char_name.replace(" ", "_")[:20]

    panel_data = list(zip(images, frames))

    if single_page:
        page_img = assemble_grid_page(panel_data, cols=grid_cols, page_width=grid_width)
        fname = f"comic_{comic_tag}_{char_tag}.png"
        fpath = os.path.join(output_dir, fname)
        page_img.convert("RGB").save(fpath)
        return [fpath]
    else:
        pages = []
        for i in range(0, len(panel_data), panels_per_page):
            pages.append(panel_data[i:i + panels_per_page])

        saved = []
        for pi, page_panels in enumerate(pages):
            page_img = assemble_page(page_panels, pi + 1)
            fname = f"comic_{comic_tag}_{char_tag}_p{pi+1:02d}.png"
            fpath = os.path.join(output_dir, fname)
            page_img.convert("RGB").save(fpath)
            saved.append(fpath)

        export_tag = f"comic_{comic_tag}_{char_tag}"
        export_pdf(saved, output_dir, export_tag)
        export_cbz(saved, output_dir, export_tag)
        return saved


def assemble_from_script(script_path: str, image_dirs: List[str],
                         output_dir: str,
                         page_width: int = SCRIPT_PAGE_WIDTH) -> List[str]:
    """Full comic-from-script pipeline: load JSON, find images, build pages, save."""
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    title = script.get("title", Path(script_path).stem)
    pages = script.get("pages", [])

    script_tag = re.sub(r"[^\w]", "_", title)[:20]
    os.makedirs(output_dir, exist_ok=True)

    saved = []
    for pi, page_def in enumerate(pages):
        page_img = assemble_scripted_page(page_def, image_dirs, script_tag, page_width)

        fname = f"comic_{script_tag}_p{pi+1:03d}.png"
        fpath = os.path.join(output_dir, fname)
        page_img.convert("RGB").save(fpath, quality=95)
        saved.append(fpath)

    export_pdf(saved, output_dir, script_tag)
    export_cbz(saved, output_dir, script_tag)
    return saved


def assemble_from_script_data(script: Dict, image_dirs: List[str],
                              output_dir: str,
                              page_width: int = SCRIPT_PAGE_WIDTH) -> List[str]:
    """Assemble pages from an already-parsed script dict (for UI use)."""
    title = script.get("title", "Untitled")
    pages = script.get("pages", [])

    script_tag = re.sub(r"[^\w]", "_", title)[:20]
    os.makedirs(output_dir, exist_ok=True)

    saved = []
    for pi, page_def in enumerate(pages):
        page_img = assemble_scripted_page(page_def, image_dirs, script_tag, page_width)

        fname = f"comic_{script_tag}_p{pi+1:03d}.png"
        fpath = os.path.join(output_dir, fname)
        page_img.convert("RGB").save(fpath, quality=95)
        saved.append(fpath)

    export_pdf(saved, output_dir, script_tag)
    export_cbz(saved, output_dir, script_tag)
    return saved


# -- export helpers ---------------------------------------------------------

def export_pdf(page_paths: List[str], output_dir: str, tag: str) -> Optional[str]:
    """Export assembled pages as a single PDF."""
    if not page_paths:
        return None
    pdf_path = os.path.join(output_dir, f"{tag}.pdf")
    images = []
    for p in page_paths:
        img = Image.open(p).convert("RGB")
        images.append(img)
    images[0].save(pdf_path, save_all=True, append_images=images[1:],
                   resolution=150)
    return pdf_path


def export_cbz(page_paths: List[str], output_dir: str, tag: str) -> Optional[str]:
    """Export assembled pages as a CBZ (comic book archive)."""
    if not page_paths:
        return None
    cbz_path = os.path.join(output_dir, f"{tag}.cbz")
    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_STORED) as zf:
        for i, p in enumerate(page_paths):
            arcname = f"{tag}_p{i+1:03d}.png"
            zf.write(p, arcname)
    return cbz_path
