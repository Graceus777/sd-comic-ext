"""Pure helpers for editing a comic script's lettering layers."""
import json
import re
from typing import Any, Dict, List, Tuple

from . import text_styles


CORE_LAYERS = {
    "dialogue": ("Dialogue bubble", text_styles.DIALOGUE_DEFAULT),
    "caption": ("Caption / narration", text_styles.CAPTION_DEFAULT),
}


def parse_script(json_str: str) -> Dict[str, Any]:
    if not json_str or not json_str.strip():
        raise ValueError("Load or create a comic script first")
    try:
        script = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid script JSON: {exc}") from exc
    if not isinstance(script, dict) or not isinstance(script.get("pages"), list):
        raise ValueError("Comic script must contain a pages array")
    return script


def panel_choices(script: Dict[str, Any]) -> List[Tuple[str, str]]:
    choices: List[Tuple[str, str]] = []
    for page_index, page in enumerate(script.get("pages", [])):
        if not isinstance(page, dict):
            continue
        panels = page.get("panels", [])
        if not isinstance(panels, list):
            continue
        for panel_index, panel in enumerate(panels):
            if not isinstance(panel, dict):
                continue
            panel_id = panel.get("id") or f"panel {panel_index + 1}"
            scene = " ".join(str(panel.get("scene", "")).split())
            if len(scene) > 46:
                scene = scene[:43] + "..."
            label = f"Page {page_index + 1} / {panel_id}"
            if scene:
                label += f" - {scene}"
            choices.append((label, f"{page_index}:{panel_index}"))
    return choices


def get_panel(script: Dict[str, Any], panel_ref: str):
    match = re.fullmatch(r"(\d+):(\d+)", str(panel_ref or ""))
    if not match:
        raise ValueError("Select a panel")
    page_index, panel_index = (int(part) for part in match.groups())
    try:
        page = script["pages"][page_index]
        panel = page["panels"][panel_index]
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("The selected panel no longer exists; refresh panels") from exc
    if not isinstance(page, dict) or not isinstance(panel, dict):
        raise ValueError("The selected panel is malformed")
    return page, panel, page_index, panel_index


def layer_choices(panel: Dict[str, Any]) -> List[Tuple[str, str]]:
    choices = [(label, key) for key, (label, _) in CORE_LAYERS.items()]
    layers = panel.get("lettering", [])
    if not isinstance(layers, list):
        return choices
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        layer_id = layer.get("id") or f"effect {index + 1}"
        text = " ".join(str(layer.get("text", "")).split())
        if len(text) > 30:
            text = text[:27] + "..."
        label = f"Extra: {layer_id}"
        if text:
            label += f" - {text}"
        choices.append((label, f"extra:{index}"))
    return choices


def _number(value, default: float, lower: float, upper: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return max(lower, min(upper, result))


def color_to_hex(value, fallback=(0, 0, 0)) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
            return raw.lower()
        if re.fullmatch(r"#[0-9a-fA-F]{3}", raw):
            return "#" + "".join(ch * 2 for ch in raw[1:]).lower()
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            rgb = [max(0, min(255, int(channel))) for channel in value[:3]]
            return "#{:02x}{:02x}{:02x}".format(*rgb)
        except (TypeError, ValueError):
            pass
    return "#{:02x}{:02x}{:02x}".format(*fallback[:3])


def style_defaults(style_name: str) -> Dict[str, Any]:
    style_name = style_name if style_name in text_styles.STYLES else text_styles.EFFECT_DEFAULT
    spec = text_styles.get_style(style_name, text_styles.EFFECT_DEFAULT)
    return {
        "style": style_name,
        "font": spec.get("font_family", "sans"),
        "anchor": spec["default_anchor"],
        "x": 0,
        "y": 0,
        "width": int(round(float(spec["default_width"]) * 100)),
        "font_size": int(spec["default_font"]),
        "rotation": int(spec.get("default_rotation", 0)),
        "color": color_to_hex(spec.get("text_fill"), (15, 15, 15)),
        "outline_color": color_to_hex(spec.get("text_stroke_fill"), (0, 0, 0)),
    }


def _extra_index(layer_ref: str) -> int:
    match = re.fullmatch(r"extra:(\d+)", str(layer_ref or ""))
    if not match:
        raise ValueError("Select a lettering layer")
    return int(match.group(1))


def layer_values(panel: Dict[str, Any], layer_ref: str) -> Dict[str, Any]:
    if layer_ref in CORE_LAYERS:
        _, fallback = CORE_LAYERS[layer_ref]
        style_name = panel.get(f"{layer_ref}_style") or fallback
        result = style_defaults(style_name)
        style_name = result["style"]
        offset = panel.get(f"{layer_ref}_offset", [0, 0])
        if not isinstance(offset, (list, tuple)) or len(offset) != 2:
            offset = [0, 0]
        result.update({
            "text": str(panel.get(layer_ref, "")),
            "font": panel.get(f"{layer_ref}_font") or result["font"],
            "anchor": panel.get(f"{layer_ref}_anchor") or result["anchor"],
            "x": offset[0],
            "y": offset[1],
            "width": panel.get(f"{layer_ref}_width") or result["width"],
            "font_size": panel.get(f"{layer_ref}_font_size") or result["font_size"],
            "rotation": panel.get(f"{layer_ref}_rotation", result["rotation"]),
            "color": color_to_hex(panel.get(f"{layer_ref}_color"), tuple(text_styles.get_style(style_name).get("text_fill", (15, 15, 15)))),
            "outline_color": color_to_hex(panel.get(f"{layer_ref}_outline_color"), tuple(text_styles.get_style(style_name).get("text_stroke_fill", (0, 0, 0)))),
        })
        return result

    index = _extra_index(layer_ref)
    layers = panel.get("lettering", [])
    try:
        layer = layers[index]
    except (IndexError, TypeError) as exc:
        raise ValueError("The selected layer no longer exists; refresh layers") from exc
    if not isinstance(layer, dict):
        raise ValueError("The selected layer is malformed")
    style_name = layer.get("style") or text_styles.EFFECT_DEFAULT
    result = style_defaults(style_name)
    style_name = result["style"]
    offset = layer.get("offset", [0, 0])
    if not isinstance(offset, (list, tuple)) or len(offset) != 2:
        offset = [0, 0]
    result.update({
        "text": str(layer.get("text", "")),
        "font": layer.get("font") or result["font"],
        "anchor": layer.get("anchor") or result["anchor"],
        "x": offset[0],
        "y": offset[1],
        "width": layer.get("width") or result["width"],
        "font_size": layer.get("font_size") or result["font_size"],
        "rotation": layer.get("rotation", result["rotation"]),
        "color": color_to_hex(layer.get("color"), tuple(text_styles.get_style(style_name).get("text_fill", (15, 15, 15)))),
        "outline_color": color_to_hex(layer.get("outline_color"), tuple(text_styles.get_style(style_name).get("text_stroke_fill", (0, 0, 0)))),
    })
    return result


def normalize_values(values: Dict[str, Any]) -> Dict[str, Any]:
    style_name = str(values.get("style") or text_styles.EFFECT_DEFAULT)
    if style_name not in text_styles.STYLES:
        style_name = text_styles.EFFECT_DEFAULT
    defaults = style_defaults(style_name)
    available_fonts = text_styles.font_families()
    font = str(values.get("font") or defaults["font"])
    if font not in available_fonts:
        font = defaults["font"]
    return {
        "text": str(values.get("text") or "").strip(),
        "style": style_name,
        "font": font,
        "anchor": text_styles.normalize_anchor(values.get("anchor"), defaults["anchor"]),
        "offset": [
            int(round(_number(values.get("x"), 0, -50, 50))),
            int(round(_number(values.get("y"), 0, -50, 50))),
        ],
        "width": int(round(_number(values.get("width"), defaults["width"], 15, 100))),
        "font_size": int(round(_number(values.get("font_size"), defaults["font_size"], 12, 140))),
        "rotation": int(round(_number(values.get("rotation"), defaults["rotation"], -45, 45))),
        "color": color_to_hex(
            values.get("color"), tuple(text_styles.get_style(style_name).get("text_fill", (15, 15, 15)))
        ),
        "outline_color": color_to_hex(
            values.get("outline_color"), tuple(text_styles.get_style(style_name).get("text_stroke_fill", (0, 0, 0)))
        ),
    }


def _next_effect_id(layers: List[Dict[str, Any]]) -> str:
    used = {str(layer.get("id")) for layer in layers if isinstance(layer, dict)}
    number = 1
    while f"fx{number}" in used:
        number += 1
    return f"fx{number}"


def set_layer(panel: Dict[str, Any], layer_ref: str, values: Dict[str, Any], *, add_new=False) -> str:
    clean = normalize_values(values)
    if add_new:
        if not clean["text"]:
            raise ValueError("Enter effect text before adding a layer")
        layers = panel.setdefault("lettering", [])
        if not isinstance(layers, list):
            layers = []
            panel["lettering"] = layers
        clean["id"] = _next_effect_id(layers)
        layers.append(clean)
        return f"extra:{len(layers) - 1}"

    if layer_ref in CORE_LAYERS:
        key = layer_ref
        if not clean["text"]:
            remove_layer(panel, layer_ref)
            return layer_ref
        panel[key] = clean.pop("text")
        panel[f"{key}_style"] = clean["style"]
        panel[f"{key}_font"] = clean["font"]
        panel[f"{key}_anchor"] = clean["anchor"]
        panel[f"{key}_offset"] = clean["offset"]
        panel[f"{key}_width"] = clean["width"]
        panel[f"{key}_font_size"] = clean["font_size"]
        panel[f"{key}_rotation"] = clean["rotation"]
        panel[f"{key}_color"] = clean["color"]
        panel[f"{key}_outline_color"] = clean["outline_color"]
        return layer_ref

    if not clean["text"]:
        remove_layer(panel, layer_ref)
        return "dialogue"
    index = _extra_index(layer_ref)
    layers = panel.get("lettering", [])
    try:
        old = layers[index]
    except (IndexError, TypeError) as exc:
        raise ValueError("The selected layer no longer exists; refresh layers") from exc
    clean["id"] = old.get("id") or _next_effect_id(layers)
    layers[index] = clean
    return layer_ref


def remove_layer(panel: Dict[str, Any], layer_ref: str) -> None:
    if layer_ref in CORE_LAYERS:
        prefix = f"{layer_ref}_"
        for key in list(panel):
            if key == layer_ref or key.startswith(prefix):
                panel.pop(key, None)
        return
    index = _extra_index(layer_ref)
    layers = panel.get("lettering", [])
    try:
        layers.pop(index)
    except (IndexError, AttributeError, TypeError) as exc:
        raise ValueError("The selected layer no longer exists; refresh layers") from exc
    if not layers:
        panel.pop("lettering", None)


def update_json(json_str: str, panel_ref: str, layer_ref: str, values: Dict[str, Any], *, add_new=False):
    script = parse_script(json_str)
    _, panel, _, _ = get_panel(script, panel_ref)
    selected = set_layer(panel, layer_ref, values, add_new=add_new)
    return json.dumps(script, indent=2, ensure_ascii=False), selected


def remove_from_json(json_str: str, panel_ref: str, layer_ref: str) -> str:
    script = parse_script(json_str)
    _, panel, _, _ = get_panel(script, panel_ref)
    remove_layer(panel, layer_ref)
    return json.dumps(script, indent=2, ensure_ascii=False)
