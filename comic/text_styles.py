"""Lettering style and font presets for the comic assembler.

Panel-level legacy fields use ``dialogue_*`` and ``caption_*``. Additional
independent layers live in ``panel["lettering"]`` and use unprefixed keys.
All sizes are authored against a 1200px-wide panel and scale at render time.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -- font families ----------------------------------------------------------

# Logical families keep comic scripts portable between machines. Users may
# add .ttf/.otf/.ttc files to the extension-local fonts/ directory.
FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"

FONT_FAMILIES: Dict[str, Dict] = {
    "comic": {
        "label": "Comic",
        "regular": [
            "C:/Windows/Fonts/comic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/comicbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
    },
    "handwritten": {
        "label": "Handwritten",
        "regular": [
            "C:/Windows/Fonts/segoepr.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/segoeprb.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ],
    },
    "impact": {
        "label": "Impact / display",
        "regular": [
            "C:/Windows/Fonts/impact.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/impact.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        ],
    },
    "sans": {
        "label": "Clean sans",
        "regular": [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
    },
    "serif": {
        "label": "Serif / narration",
        "regular": [
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/georgia.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/timesbd.ttf",
            "C:/Windows/Fonts/georgiab.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ],
    },
    "mono": {
        "label": "Monospace / machine",
        "regular": [
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/cour.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/consolab.ttf",
            "C:/Windows/Fonts/courbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        ],
    },
}


def _custom_fonts() -> Dict[str, Dict]:
    found: Dict[str, Dict] = {}
    if not FONT_DIR.is_dir():
        return found
    try:
        files = sorted(
            p for p in FONT_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in {".ttf", ".otf", ".ttc"}
        )
    except OSError:
        return found
    for path in files:
        key = f"custom:{path.stem}"
        found[key] = {
            "label": f"Custom: {path.stem}",
            "regular": [str(path)],
            "bold": [str(path)],
        }
    return found


def font_families() -> Dict[str, Dict]:
    families = dict(FONT_FAMILIES)
    families.update(_custom_fonts())
    return families


def font_choices() -> List[Tuple[str, str]]:
    return [(spec["label"], key) for key, spec in font_families().items()]


def resolve_font_path(family: Optional[str], bold: bool = False) -> Optional[str]:
    """Resolve a logical font family to an installed font file."""
    families = font_families()
    key = str(family or "").strip()
    spec = families.get(key) or families["sans"]
    candidates = list(spec["bold" if bold else "regular"])
    if bold:
        candidates.extend(spec["regular"])
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    for fallback in families.values():
        for candidate in fallback["bold" if bold else "regular"]:
            if os.path.isfile(candidate):
                return candidate
    return None


# -- anchors ----------------------------------------------------------------

ANCHORS: List[str] = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

ANCHOR_ALIASES: Dict[str, str] = {
    "top": "top-center",
    "bottom": "bottom-center",
    "left": "center-left",
    "right": "center-right",
    "middle": "center",
    "centre": "center",
    "": "bottom-center",
}


def normalize_anchor(anchor: Optional[str], fallback: str = "bottom-center") -> str:
    if not anchor:
        return fallback
    value = str(anchor).strip().lower().replace(" ", "-").replace("_", "-")
    value = ANCHOR_ALIASES.get(value, value)
    return value if value in ANCHORS else fallback


# -- style registry ---------------------------------------------------------

DIALOGUE_DEFAULT = "speech"
CAPTION_DEFAULT = "narration"
EFFECT_DEFAULT = "sfx"

STYLES: Dict[str, Dict] = {
    "speech": {
        "label": "Speech (rounded)",
        "shape": "rounded", "radius": 18,
        "fill": (255, 255, 255, 235), "outline": (25, 25, 25, 220), "outline_width": 3,
        "text_fill": (15, 15, 15), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "triangle",
        "default_anchor": "bottom-center", "default_width": 0.74,
        "default_font": 30, "font_family": "comic", "default_rotation": 0, "padding": 16,
    },
    "thought": {
        "label": "Thought (cloud)",
        "shape": "cloud", "radius": 22,
        "fill": (255, 255, 255, 235), "outline": (60, 60, 70, 210), "outline_width": 3,
        "text_fill": (35, 35, 45), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "dots",
        "default_anchor": "top-center", "default_width": 0.62,
        "default_font": 28, "font_family": "handwritten", "default_rotation": 0, "padding": 20,
    },
    "shout": {
        "label": "Exclamation / shout (burst)",
        "shape": "spiky", "radius": 0,
        "fill": (255, 255, 255, 240), "outline": (10, 10, 10, 255), "outline_width": 4,
        "text_fill": (10, 10, 10), "bold": True, "all_caps": True,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "jagged",
        "default_anchor": "center", "default_width": 0.64,
        "default_font": 32, "font_family": "impact", "default_rotation": -3, "padding": 24,
    },
    "whisper": {
        "label": "Whisper (dashed)",
        "shape": "dashed", "radius": 18,
        "fill": (255, 255, 255, 170), "outline": (90, 90, 90, 190), "outline_width": 2,
        "text_fill": (70, 70, 70), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "triangle",
        "default_anchor": "bottom-center", "default_width": 0.56,
        "default_font": 26, "font_family": "handwritten", "default_rotation": 0, "padding": 14,
    },
    "radio": {
        "label": "Radio / off-panel",
        "shape": "rect", "radius": 0,
        "fill": (235, 240, 255, 235), "outline": (40, 60, 120, 235), "outline_width": 3,
        "text_fill": (20, 30, 70), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "jagged",
        "default_anchor": "bottom-right", "default_width": 0.5,
        "default_font": 26, "font_family": "mono", "default_rotation": 0, "padding": 14,
    },
    "narration": {
        "label": "Narration bar (top)",
        "shape": "rect", "radius": 0,
        "fill": (10, 10, 20, 200), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (230, 225, 210), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "none",
        "default_anchor": "top-center", "default_width": 1.0,
        "default_font": 32, "font_family": "serif", "default_rotation": 0, "padding": 16,
    },
    "caption_box": {
        "label": "Caption box (white)",
        "shape": "rect", "radius": 0,
        "fill": (255, 255, 255, 235), "outline": (20, 20, 20, 220), "outline_width": 2,
        "text_fill": (15, 15, 15), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "none",
        "default_anchor": "top-left", "default_width": 0.46,
        "default_font": 26, "font_family": "sans", "default_rotation": 0, "padding": 14,
    },
    "yellow_box": {
        "label": "Caption box (yellow)",
        "shape": "rect", "radius": 0,
        "fill": (245, 224, 92, 240), "outline": (50, 38, 0, 220), "outline_width": 2,
        "text_fill": (25, 18, 0), "bold": True, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "none",
        "default_anchor": "top-left", "default_width": 0.46,
        "default_font": 26, "font_family": "comic", "default_rotation": 0, "padding": 14,
    },
    "parchment": {
        "label": "Parchment box",
        "shape": "rounded", "radius": 10,
        "fill": (224, 206, 160, 242), "outline": (120, 90, 50, 230), "outline_width": 2,
        "text_fill": (60, 40, 20), "bold": False, "all_caps": False,
        "text_stroke": 0, "text_stroke_fill": (0, 0, 0), "tail": "none",
        "default_anchor": "top-left", "default_width": 0.5,
        "default_font": 28, "font_family": "serif", "default_rotation": 0, "padding": 16,
    },
    "sfx": {
        "label": "SFX: classic impact (no box)",
        "shape": "plain", "radius": 0,
        "fill": (0, 0, 0, 0), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (255, 232, 90), "bold": True, "all_caps": True,
        "text_stroke": 5, "text_stroke_fill": (20, 20, 20), "tail": "none",
        "default_anchor": "center", "default_width": 0.9,
        "default_font": 52, "font_family": "impact", "default_rotation": -7, "padding": 8,
    },
    "sfx_speed": {
        "label": "SFX: speed / whoosh (no box)",
        "shape": "plain", "radius": 0,
        "fill": (0, 0, 0, 0), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (215, 245, 255), "bold": True, "all_caps": True,
        "text_stroke": 4, "text_stroke_fill": (20, 65, 100), "tail": "none",
        "default_anchor": "center-right", "default_width": 0.68,
        "default_font": 48, "font_family": "sans", "default_rotation": -12, "padding": 8,
    },
    "sfx_horror": {
        "label": "SFX: horror / menace (no box)",
        "shape": "plain", "radius": 0,
        "fill": (0, 0, 0, 0), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (205, 30, 35), "bold": True, "all_caps": True,
        "text_stroke": 5, "text_stroke_fill": (15, 0, 0), "tail": "none",
        "default_anchor": "bottom-center", "default_width": 0.78,
        "default_font": 54, "font_family": "serif", "default_rotation": 2, "padding": 8,
    },
    "sfx_electric": {
        "label": "SFX: electric / energy (no box)",
        "shape": "plain", "radius": 0,
        "fill": (0, 0, 0, 0), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (245, 250, 255), "bold": True, "all_caps": True,
        "text_stroke": 5, "text_stroke_fill": (35, 85, 230), "tail": "none",
        "default_anchor": "center", "default_width": 0.82,
        "default_font": 50, "font_family": "impact", "default_rotation": 6, "padding": 8,
    },
    "sfx_subtle": {
        "label": "SFX: subtle / ambient (no box)",
        "shape": "plain", "radius": 0,
        "fill": (0, 0, 0, 0), "outline": (0, 0, 0, 0), "outline_width": 0,
        "text_fill": (235, 235, 235), "bold": False, "all_caps": False,
        "text_stroke": 2, "text_stroke_fill": (35, 35, 35), "tail": "none",
        "default_anchor": "bottom-right", "default_width": 0.5,
        "default_font": 28, "font_family": "handwritten", "default_rotation": 4, "padding": 8,
    },
}

BUBBLE_STYLE_NAMES = ["speech", "thought", "shout", "whisper", "radio"]
CAPTION_STYLE_NAMES = ["narration", "caption_box", "yellow_box", "parchment"]
EFFECT_STYLE_NAMES = ["sfx", "sfx_speed", "sfx_horror", "sfx_electric", "sfx_subtle"]
# Build Page has one dialogue field, so it also exposes boxless effects there.
DIALOGUE_STYLE_NAMES = BUBBLE_STYLE_NAMES + EFFECT_STYLE_NAMES
ALL_STYLE_NAMES = BUBBLE_STYLE_NAMES + CAPTION_STYLE_NAMES + EFFECT_STYLE_NAMES


def get_style(name: Optional[str], fallback: str = DIALOGUE_DEFAULT) -> Dict:
    """Return a copy of a style, falling back safely for unknown names."""
    key = str(name or "").strip().lower()
    spec = STYLES.get(key) or STYLES.get(fallback) or STYLES[DIALOGUE_DEFAULT]
    return dict(spec)


def style_choices(names: List[str]) -> List[Tuple[str, str]]:
    return [(STYLES[name]["label"], name) for name in names if name in STYLES]
