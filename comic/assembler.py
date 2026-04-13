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

def get_font(size: int, bold: bool = False):
    """Try to load a decent font, fall back to default."""
    if bold:
        candidates = [
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for fp in candidates:
        if os.path.isfile(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


FONT_CAPTION = get_font(32, bold=False)
FONT_DIALOGUE = get_font(30, bold=False)
FONT_LABEL = get_font(22, bold=True)

_font_cache: Dict = {}


def _scaled_font(base_size: int, panel_w: int, bold: bool = False):
    """Get a font scaled to panel width. Base sizes designed for ~1200px panels."""
    size = max(16, min(52, int(base_size * panel_w / 1200)))
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = get_font(size, bold)
    return _font_cache[key]


# -- drawing helpers --------------------------------------------------------

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def draw_caption_overlay(panel: Image.Image, text: str, font=None):
    """Draw a dark translucent caption bar at the top of a panel image."""
    if font is None:
        font = FONT_CAPTION
    draw = ImageDraw.Draw(panel)
    pw = panel.width
    padding = 16
    line_h = int(font.size * 1.2) if hasattr(font, 'size') else 38

    lines = wrap_text(text, font, pw - padding * 2, draw)
    box_h = padding * 2 + line_h * len(lines)

    overlay = Image.new("RGBA", (pw, box_h), (10, 10, 20, 200))
    panel.paste(Image.alpha_composite(
        Image.new("RGBA", (pw, box_h), (0, 0, 0, 0)), overlay
    ), (0, 0))

    draw = ImageDraw.Draw(panel)
    ty = padding
    for line in lines:
        draw.text((padding, ty), line, fill=(230, 225, 210), font=font)
        ty += line_h


def draw_dialogue_overlay(panel: Image.Image, text: str, font=None):
    """Draw a white speech bubble overlaid at the bottom of a panel image."""
    if font is None:
        font = FONT_DIALOGUE
    pw, ph = panel.size
    padding = 16
    line_h = int(font.size * 1.2) if hasattr(font, 'size') else 36
    margin_x = 40
    margin_bottom = 30

    tmp_draw = ImageDraw.Draw(panel)
    bub_w = pw - margin_x * 2
    lines = wrap_text(text, font, bub_w - padding * 2, tmp_draw)
    bub_h = padding * 2 + line_h * len(lines)

    bub_x = margin_x
    bub_y = ph - bub_h - margin_bottom

    overlay = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    odraw.rounded_rectangle(
        [(bub_x, bub_y), (bub_x + bub_w, bub_y + bub_h)],
        radius=16, fill=(255, 255, 255, 220), outline=(30, 30, 30, 180), width=3
    )
    # tail
    tail_cx = bub_x + bub_w // 3
    tail_pts = [
        (tail_cx, bub_y + bub_h),
        (tail_cx + 12, bub_y + bub_h + 18),
        (tail_cx + 28, bub_y + bub_h),
    ]
    odraw.polygon(tail_pts, fill=(255, 255, 255, 220), outline=(30, 30, 30, 180))

    panel_composite = Image.alpha_composite(panel, overlay)
    panel.paste(panel_composite)

    draw = ImageDraw.Draw(panel)
    ty = bub_y + padding
    for line in lines:
        draw.text((bub_x + padding, ty), line, fill=(15, 15, 15), font=font)
        ty += line_h


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

    caption = frame.get("caption", "")
    dialogue = frame.get("dialogue", "")

    if caption:
        draw_caption_overlay(im, caption)
    if dialogue:
        draw_dialogue_overlay(im, dialogue)

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

    caption = panel.get("caption", "")
    dialogue = panel.get("dialogue", "")

    if caption and caption.strip() and caption.strip() != "...":
        cap_font = _scaled_font(32, slot_w)
        draw_caption_overlay(im, caption, font=cap_font)
    if dialogue and dialogue.strip() and dialogue.strip() != "...":
        dlg_font = _scaled_font(30, slot_w)
        draw_dialogue_overlay(im, dialogue, font=dlg_font)

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
