"""
Shot type vocabulary, inference, and prompt construction for comic panels.

Ported from generate_comic.py — camera vocabulary tokens, shot inference,
continuity validation, and panel prompt assembly.
"""
import re
import hashlib
from typing import Any, Dict, List, Optional


# -- shot type vocabulary ---------------------------------------------------

SHOT_DICTION = {
    "extreme_close_up": [
        "extreme close-up, macro detail",
        "ultra tight close-up, detail focus",
        "extreme close-up, filling frame",
    ],
    "close_up": [
        "close-up, portrait",
        "tight close-up, head shot",
        "head and shoulders close-up",
    ],
    "medium_close": [
        "medium close-up, upper body",
        "bust shot, upper body",
        "chest-up close shot",
    ],
    "medium": [
        "medium shot, waist up",
        "cowboy shot",
        "half-body medium shot",
    ],
    "full_body": [
        "full body, head to toe",
        "full-length shot, entire figure",
        "full body, feet visible",
    ],
    "wide": [
        "wide shot, environment visible",
        "wide angle establishing shot",
        "long shot, figure in scene",
    ],
    "low_angle": [
        "low angle, from below",
        "worms eye view, looking up",
        "dramatic low angle shot",
    ],
    "high_angle": [
        "high angle, from above",
        "birds eye view",
        "overhead angle shot",
    ],
    "from_behind": [
        "from behind, rear view",
        "back view, from behind",
        "viewed from behind",
    ],
    "side_profile": [
        "profile view, from side",
        "side profile shot",
        "lateral view, side angle",
    ],
    "insert": [
        "insert shot, detail focus",
        "detail shot, object close-up",
        "object focus, tight framing",
    ],
}

_SHOT_INFERENCE = [
    ("extreme_close_up", ["extreme close-up", "extreme close up", "macro"]),
    ("low_angle", ["low angle", "from below", "worms eye", "looking up at"]),
    ("high_angle", ["high angle", "from above", "birds eye", "overhead"]),
    ("from_behind", ["from behind", "back view", "rear view"]),
    ("side_profile", ["side profile", "profile view", "from side"]),
    ("insert", ["insert shot", "detail shot", "object focus"]),
    ("close_up", ["close-up", "close up", "portrait", "face focus", "headshot"]),
    ("medium_close", ["upper body", "bust shot", "chest up"]),
    ("full_body", ["full body", "full figure", "full length", "head to toe", "feet visible"]),
    ("wide", ["wide shot", "wide angle", "establishing shot", "panorama", "scenery"]),
    ("medium", ["medium shot", "cowboy shot", "waist up", "mid shot"]),
]

_SHOT_ADJACENCY = {
    "extreme_close_up": {"close_up", "insert"},
    "close_up": {"extreme_close_up", "medium_close", "medium", "insert"},
    "medium_close": {"close_up", "medium"},
    "medium": {"medium_close", "close_up", "full_body", "from_behind", "side_profile"},
    "full_body": {"medium", "wide", "low_angle", "high_angle", "from_behind"},
    "wide": {"full_body", "medium", "high_angle"},
    "low_angle": {"medium", "full_body", "close_up"},
    "high_angle": {"wide", "full_body", "medium"},
    "from_behind": {"medium", "full_body", "side_profile"},
    "side_profile": {"close_up", "medium", "from_behind"},
    "insert": {"close_up", "extreme_close_up"},
}

# Layouts where panels fill most of the page width (benefit from hires)
LARGE_SLOT_LAYOUTS = {"splash", "two_row", "wide_focus"}


def infer_shot_type(scene: str, positive_extra: str = "", no_character: bool = False) -> str:
    text = f"{scene} {positive_extra}".lower()
    for shot_type, keywords in _SHOT_INFERENCE:
        for kw in keywords:
            if kw in text:
                return shot_type
    return "wide" if no_character else "medium"


def get_shot_token(shot_type: str, variant_index: int = 0) -> str:
    variants = SHOT_DICTION.get(shot_type, SHOT_DICTION["medium"])
    return variants[variant_index % len(variants)]


def validate_camera_continuity(script: Dict[str, Any]) -> List[str]:
    warnings = []
    for page in script.get("pages", []):
        prev_shot = None
        prev_id = None
        for panel in page.get("panels", []):
            shot = panel.get("shot") or infer_shot_type(
                panel.get("scene", ""), panel.get("positive_extra", ""),
                panel.get("no_character", False),
            )
            if prev_shot and shot != prev_shot:
                allowed = _SHOT_ADJACENCY.get(prev_shot, set())
                if shot not in allowed:
                    warnings.append(
                        f"  {prev_id} ({prev_shot}) -> {panel.get('id')} ({shot}): "
                        f"jarring cut (expected {', '.join(sorted(allowed))})"
                    )
            prev_shot = shot
            prev_id = panel.get("id")
    return warnings


def panel_needs_auto_hires(panel: Dict, page: Dict) -> bool:
    layout = page.get("layout", "").lower().replace("-", "_")
    if layout in LARGE_SLOT_LAYOUTS:
        return True
    if layout == "t_top" and page["panels"][0].get("id") == panel.get("id"):
        return True
    if layout == "t_bottom" and page["panels"][-1].get("id") == panel.get("id"):
        return True
    return False


# -- seed computation -------------------------------------------------------

def compute_page_seed(title: str, page_index: int) -> int:
    key = f"{title}:page:{page_index}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def compute_scene_seed(title: str, scene_name: str) -> int:
    key = f"{title}:scene:{scene_name}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


# -- prompt construction ----------------------------------------------------

def build_panel_prompt(
    character: Optional[Dict[str, Any]],
    panel: Dict[str, Any],
    base_positive: str,
    shot_token: str = "",
) -> str:
    """
    Assemble the positive prompt for a single panel.

    Order (character):  <lora>, base_positive, activation, 1girl, [shot_token], scene, extra
    Order (no_char):    base_positive (stripped), scene, extra, no people tags
    """
    parts: List[str] = []
    no_char = character is None

    if not no_char:
        lora_name = character.get("lora", "")
        weight = character.get("weight", 0.8)
        activation = character.get("activation", "")

        if lora_name:
            parts.append(f"<lora:{lora_name}:{weight}>")

        if base_positive:
            bp = re.sub(r',?\s*1girl\s*,?\s*', ', ', base_positive)
            bp = re.sub(r',?\s*solo\s*,?\s*', ', ', bp)
            bp = re.sub(r',\s*,', ',', bp).strip(', ')
            parts.append(bp)

        if activation:
            parts.append(activation)
        parts.append("1girl")
    else:
        strip_tags = [r'1girl', r'solo', r'detailed skin', r'detailed face',
                      r'beautiful', r'aesthetic']
        bp = base_positive
        for tag in strip_tags:
            bp = re.sub(rf',?\s*{tag}\s*,?\s*', ', ', bp)
        bp = re.sub(r',\s*,', ',', bp).strip(', ')
        parts.append(bp)

    if shot_token:
        scene_lower = f"{panel.get('scene', '')} {panel.get('positive_extra', '')}".lower()
        core = shot_token.split(",")[0].strip().lower()
        if core not in scene_lower:
            parts.append(shot_token)

    if panel.get("scene"):
        parts.append(panel["scene"])
    if panel.get("positive_extra"):
        parts.append(panel["positive_extra"])

    if no_char:
        parts.append("no people, no person, no humans, scenery, background")

    return ", ".join(parts)
