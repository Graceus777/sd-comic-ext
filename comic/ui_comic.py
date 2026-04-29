"""
Gradio UI for the Comic Generator tab.

Two sub-tabs:
  1. Comic — JSON editor for authored scripts, generate panels, assemble pages
  2. Assembly — standalone re-assembly from existing images, export PDF/CBZ

Strip scripts are available via the Comic tab's "Load script file" dropdown
(select an "(Example)" preset or load a saved strip script JSON directly).
"""
import json
import os
import threading
from typing import List, Optional

import gradio as gr

from comic.shared import EXT_DIR, STRIPS_DIR, DEFAULT_CONFIG
from comic import comic_engine
from comic import assembler
from comic.prompt_builder import validate_camera_continuity
from comic.ui_wizard import (
    _build_template,
    _list_characters,
    FORMATS,
    FORMAT_LABELS,
)


# -- shared state -----------------------------------------------------------

_log_lines: List[str] = []
_generating = False
_lock = threading.Lock()


def _log(msg: str):
    with _lock:
        _log_lines.append(msg)


def _get_log() -> str:
    with _lock:
        return "\n".join(_log_lines)


def _clear_log():
    with _lock:
        _log_lines.clear()


def _stop():
    try:
        from modules import shared
        shared.state.interrupted = True
        return "Interrupt requested..."
    except Exception:
        return "Could not send interrupt signal"


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT / BUILD-PAGE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

LAYOUT_PANEL_COUNTS = {
    "splash":    1,
    "wide_focus":1,
    "two_row":   2,
    "three_row": 3,
    "l_right":   3,
    "l_left":    3,
    "grid_2x2":  4,
    "t_top":     4,
    "t_bottom":  4,
}

LAYOUTS = list(LAYOUT_PANEL_COUNTS.keys())

SHOT_TYPES = [
    "medium", "close_up", "wide", "full_body", "medium_close",
    "extreme_close_up", "low_angle", "high_angle", "from_behind",
    "side_profile", "insert",
]


# ═══════════════════════════════════════════════════════════════════════════
# COMIC SUB-TAB — script helpers
# ═══════════════════════════════════════════════════════════════════════════

# Built-in example scripts shown at the top of the load dropdown
_EXAMPLE_STRIP = {
    "title": "Example Strip",
    "character": {
        "lora": "your_lora_name",
        "activation": "your activation text, red dress, long hair",
        "weight": 0.8
    },
    "generation": {
        "steps": 27,
        "cfg": 6.0,
        "width": 1024,
        "height": 1280,
        "sampler": "Euler a",
        "base_positive": "masterpiece, best quality, sharp focus",
        "base_negative": "(low quality, worst quality:1.4)"
    },
    "pages": [
        {
            "layout": "three_row",
            "panels": [
                {
                    "id": "p0101",
                    "scene": "Coffee shop interior, morning light. She sits alone at a small table by the window, staring out at the rain.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": "Monday again."
                },
                {
                    "id": "p0102",
                    "scene": "Close on her face, tired but amused, as she notices the barista sliding a note under her cup.",
                    "shot": "close_up",
                    "dialogue": "Free refill?",
                    "caption": ""
                },
                {
                    "id": "p0103",
                    "scene": "She smiles for the first time, rain still falling outside, steam rising from the cup.",
                    "shot": "medium",
                    "dialogue": "Maybe Mondays aren't so bad.",
                    "caption": ""
                }
            ]
        }
    ]
}

_EXAMPLE_SHORT = {
    "title": "Example Short Story",
    "character": {
        "lora": "your_lora_name",
        "activation": "your activation text, casual clothes",
        "weight": 0.8
    },
    "generation": {
        "steps": 27,
        "cfg": 6.0,
        "width": 1024,
        "height": 1280,
        "sampler": "Euler a",
        "base_positive": "masterpiece, best quality, sharp focus",
        "base_negative": "(low quality, worst quality:1.4)"
    },
    "pages": [
        {
            "layout": "t_top",
            "panels": [
                {
                    "id": "p0101",
                    "scene": "Wide establishing shot. Rooftop garden at sunset, city skyline behind. She tends to potted herbs.",
                    "shot": "wide",
                    "dialogue": "",
                    "caption": "She'd built something quiet here, above the noise."
                },
                {
                    "id": "p0102",
                    "scene": "Close on her hands pulling weeds, soil-dusted gloves.",
                    "shot": "close_up",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0103",
                    "scene": "She looks up sharply — a pigeon has landed on her prize tomato plant.",
                    "shot": "medium",
                    "dialogue": "Hey!",
                    "caption": ""
                },
                {
                    "id": "p0104",
                    "scene": "The pigeon stares back, unbothered, tomato in its beak.",
                    "shot": "close_up",
                    "dialogue": "",
                    "caption": ""
                }
            ]
        },
        {
            "layout": "three_row",
            "panels": [
                {
                    "id": "p0201",
                    "scene": "She lunges forward, arms wide, trying to shoo the bird away.",
                    "shot": "full_body",
                    "dialogue": "Drop it! That's my best one!",
                    "caption": ""
                },
                {
                    "id": "p0202",
                    "scene": "Wide shot — pigeon flies off, tomato intact. She's left standing with her arms outstretched, hair blown back.",
                    "shot": "wide",
                    "dialogue": "",
                    "caption": "The pigeon was unbothered."
                },
                {
                    "id": "p0203",
                    "scene": "She slumps back into her garden chair, defeated but smiling slightly, looking out at the city.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": "Some things, you just can't win."
                }
            ]
        }
    ]
}

_EXAMPLE_LIBRARY = {
    "title": "Example — Library After Hours",
    "character": {
        "lora": "your_lora_name",
        "activation": "your activation text, cardigan, reading glasses",
        "weight": 0.8
    },
    "generation": {
        "steps": 27,
        "cfg": 6.0,
        "width": 1024,
        "height": 1280,
        "sampler": "Euler a",
        "base_positive": "masterpiece, best quality, sharp focus",
        "base_negative": "(low quality, worst quality:1.4)"
    },
    "pages": [
        {
            "layout": "three_row",
            "panels": [
                {
                    "id": "p0101",
                    "scene": "Wide library interior at golden hour. She sits curled in a leather armchair, open book on her lap, completely absorbed. Warm reading lamp beside her, tall bookshelves lining every wall.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": "The library closed ten minutes ago. She hadn't noticed."
                },
                {
                    "id": "p0102",
                    "scene": "She stands on tiptoe in the stacks, arm stretched up to reach a spine on the highest shelf. Late evening light catches her hair. The row of books stretches deep behind her.",
                    "shot": "full_body",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0103",
                    "scene": "She looks back over her shoulder toward the door, book clutched to her chest, a mix of surprise and amusement on her face. The reading lamps behind her are dimming one by one.",
                    "shot": "medium_close",
                    "dialogue": "I didn't hear the door lock.",
                    "caption": ""
                }
            ]
        }
    ]
}

_EXAMPLE_NIGHT_SHIFT = {
    "title": "Example — Night Shift",
    "character": {
        "lora": "your_lora_name",
        "activation": "your activation text, scrubs, stethoscope",
        "weight": 0.8
    },
    "generation": {
        "steps": 27,
        "cfg": 6.0,
        "width": 1024,
        "height": 1280,
        "sampler": "Euler a",
        "base_positive": "masterpiece, best quality, sharp focus",
        "base_negative": "(low quality, worst quality:1.4)"
    },
    "pages": [
        {
            "layout": "t_top",
            "panels": [
                {
                    "id": "p0101",
                    "scene": "Wide empty hospital corridor at 3 AM. Fluorescent lights cast long cold shadows down the hallway. Total silence except for a distant monitor beeping.",
                    "shot": "wide",
                    "dialogue": "",
                    "caption": "3:14 AM. The ward had been quiet for hours."
                },
                {
                    "id": "p0102",
                    "scene": "She stands at the nurses station, leaning over the counter, checking charts. Pen held between her teeth, monitors glowing blue behind her, empty coffee cup at her elbow.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0103",
                    "scene": "Close on a heart monitor screen. Steady green waveform. Her reflection faintly visible in the glass.",
                    "shot": "close_up",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0104",
                    "scene": "She turns sharply in the corridor, startled, hand pressed to her chest. Stethoscope swinging. Privacy curtains lining both walls. Green exit sign glowing far at the end of the hall.",
                    "shot": "full_body",
                    "dialogue": "You scared me. Nobody's supposed to be on this floor.",
                    "caption": ""
                }
            ]
        },
        {
            "layout": "three_row",
            "panels": [
                {
                    "id": "p0201",
                    "scene": "She sits on the edge of a hospital bed in an empty bay, legs dangling, slowly pulling the stethoscope from around her neck. Looking up. Tired but curious.",
                    "shot": "medium",
                    "dialogue": "Visiting hours ended at nine.",
                    "caption": ""
                },
                {
                    "id": "p0202",
                    "scene": "Close on her face. Blue glow from nearby monitors. Eyes distant, thoughtful. A strand of hair escapes her bun.",
                    "shot": "close_up",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0203",
                    "scene": "The pager on the bedside table suddenly lights up. Wide shot: she's already back on her feet, stethoscope back around her neck, walking toward the corridor door without looking back.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": "The pager buzzed. She was already gone."
                }
            ]
        }
    ]
}

_EXAMPLE_AFTER_SERVICE = {
    "title": "Example — After Service",
    "character": {
        "lora": "your_lora_name",
        "activation": "your activation text, chef coat, apron",
        "weight": 0.8
    },
    "generation": {
        "steps": 27,
        "cfg": 6.0,
        "width": 1024,
        "height": 1280,
        "sampler": "Euler a",
        "base_positive": "masterpiece, best quality, sharp focus",
        "base_negative": "(low quality, worst quality:1.4)"
    },
    "pages": [
        {
            "layout": "t_top",
            "panels": [
                {
                    "id": "p0101",
                    "scene": "Wide shot of a commercial kitchen after the last dinner service. Stainless steel gleams under harsh fluorescent lights. Steam still drifts from the pots. Everything quiet after hours of noise.",
                    "shot": "wide",
                    "dialogue": "",
                    "caption": "Last ticket cleared at 11:47. Clean-down could wait."
                },
                {
                    "id": "p0102",
                    "scene": "She leans against the steel prep counter, chef coat unbuttoned at the collar, wiping her forehead with the back of her hand. Exhausted but satisfied.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0103",
                    "scene": "Close on a perfectly plated dessert ramekin left on the pass. Her finger hovers just above it, deciding.",
                    "shot": "close_up",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0104",
                    "scene": "She sits on an overturned milk crate in the kitchen corner, legs stretched out, untying her apron strings. Copper pots hang above her. She stares at nothing.",
                    "shot": "full_body",
                    "dialogue": "",
                    "caption": ""
                }
            ]
        },
        {
            "layout": "three_row",
            "panels": [
                {
                    "id": "p0201",
                    "scene": "She turns from the dish station, hands still wet, soap suds on her forearms. Surprised to see someone still in the kitchen. Kitchen towel slung over her shoulder.",
                    "shot": "medium_close",
                    "dialogue": "I thought everyone left already.",
                    "caption": ""
                },
                {
                    "id": "p0202",
                    "scene": "She's perched up on the steel prep counter, legs swinging freely, chef coat open. The long kitchen stretches behind her, copper pots and hanging ladles framing the shot.",
                    "shot": "medium",
                    "dialogue": "",
                    "caption": ""
                },
                {
                    "id": "p0203",
                    "scene": "Wide shot. She hops off the counter, apron bundled in her arms, satisfied grin on her face. Behind her, the overhead fluorescent lights click off one by one as she walks toward the exit.",
                    "shot": "wide",
                    "dialogue": "",
                    "caption": "Some nights, the kitchen gives back."
                }
            ]
        }
    ]
}

_BUILT_IN_EXAMPLES = {
    "(Example) 3-Panel Strip": json.dumps(_EXAMPLE_STRIP, indent=2, ensure_ascii=False),
    "(Example) 7-Panel Short Story": json.dumps(_EXAMPLE_SHORT, indent=2, ensure_ascii=False),
    "(Example) Library After Hours": json.dumps(_EXAMPLE_LIBRARY, indent=2, ensure_ascii=False),
    "(Example) Night Shift": json.dumps(_EXAMPLE_NIGHT_SHIFT, indent=2, ensure_ascii=False),
    "(Example) After Service": json.dumps(_EXAMPLE_AFTER_SERVICE, indent=2, ensure_ascii=False),
}


COMICS_DIR = EXT_DIR.parent.parent / "comics"


def _list_script_files() -> List[str]:
    """Return built-in examples first, then any .json files in the comics directory."""
    found = list(_BUILT_IN_EXAMPLES.keys())
    search_dirs = [str(COMICS_DIR), str(EXT_DIR / "configs")]
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith(".json"):
                    found.append(os.path.join(root, f))
    return found


def _load_script_file(path: str) -> str:
    """Load a script: built-in examples or file path."""
    if not path:
        return ""
    if path in _BUILT_IN_EXAMPLES:
        return _BUILT_IN_EXAMPLES[path]
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _save_script_file(json_str: str, filename: str, save_dir_str: str) -> str:
    """Save the current script editor contents to the specified directory."""
    if not json_str.strip():
        return "Nothing to save — editor is empty."
    filename = filename.strip()
    if not filename:
        return "Enter a filename first."
    if not filename.endswith(".json"):
        filename += ".json"
    from pathlib import Path as _Path
    save_dir = _Path(save_dir_str.strip()) if save_dir_str.strip() else COMICS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / filename
    try:
        json.loads(json_str)  # validate JSON before saving
    except json.JSONDecodeError as e:
        return f"JSON error — not saved: {e}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)
    return f"Saved → {path}"


def _validate_script(json_str: str) -> str:
    if not json_str.strip():
        return (
            '<div style="background:#1a1a2e;border-left:4px solid #888;'
            'padding:8px 14px;border-radius:4px;">No script loaded</div>'
        )
    try:
        script = comic_engine.load_script_from_json(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return (
            '<div style="background:#2a0a0a;border-left:4px solid #f44336;'
            'padding:8px 14px;border-radius:4px;">'
            f"<b>✗ Invalid</b><br><code>{e}</code></div>"
        )
    preview = comic_engine.preview_script(script, source_label="Editor")

    # Check layout/panel-count mismatches
    layout_warnings = []
    for i, page in enumerate(script.get("pages", [])):
        layout = page.get("layout", "")
        expected = LAYOUT_PANEL_COUNTS.get(layout)
        actual = len(page.get("panels", []))
        if expected is not None and actual != expected:
            layout_warnings.append(
                f"Page {i+1}: layout <b>{layout}</b> expects {expected} panel(s) but has {actual}"
            )

    valid_header = (
        '<div style="background:#0a2a0a;border-left:4px solid #4caf50;'
        'padding:8px 14px;border-radius:4px;margin-bottom:10px;">'
        "<b>✓ Valid script</b></div>"
    )
    if layout_warnings:
        warn_block = (
            '<div style="background:#2a1f00;border-left:4px solid #ff9800;'
            'padding:8px 14px;border-radius:4px;margin-bottom:10px;">'
            "<b>⚠ Layout/panel count mismatch</b><br>"
            + "<br>".join(layout_warnings)
            + "</div>"
        )
        return warn_block + valid_header + "\n\n" + preview
    return valid_header + "\n\n" + preview


def _list_ad_models():
    """Return available ADetailer detector models for the dropdown."""
    try:
        from comic.generation_engine import list_adetailer_models
        return list_adetailer_models()
    except Exception:
        return [
            "face_yolov8n.pt", "face_yolov8s.pt",
            "hand_yolov8n.pt", "person_yolov8n-seg.pt",
            "mediapipe_face_full", "mediapipe_face_short",
        ]


def _generate_comic_panels(
    json_str, output_dir, candidates, cooldown, skip_existing, composite,
    only_panels_str,
    ad_enabled, ad_model, ad_prompt, ad_negative_prompt,
    ad_confidence, ad_denoising_strength,
    ad_mask_blur, ad_dilate_erode,
    ad_inpaint_only_masked, ad_inpaint_only_masked_padding,
):
    global _generating
    _clear_log()

    if not json_str.strip():
        return "No script loaded", []

    try:
        script = comic_engine.load_script_from_json(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return f"Script error: {e}", []

    if not output_dir.strip():
        title = script.get("title", "untitled")
        tag = comic_engine.make_title_tag(title)
        output_dir = os.path.join("comics", tag, "pages")

    only_panels = None
    if only_panels_str and only_panels_str.strip():
        only_panels = set(only_panels_str.strip().split())

    # Build ADetailer settings dict (None = disabled, let engine use defaults)
    adetailer_settings = None
    if ad_enabled:
        adetailer_settings = {
            "ad_model": ad_model or "face_yolov8n.pt",
        }
        if ad_prompt and ad_prompt.strip():
            adetailer_settings["ad_prompt"] = ad_prompt.strip()
        if ad_negative_prompt and ad_negative_prompt.strip():
            adetailer_settings["ad_negative_prompt"] = ad_negative_prompt.strip()
        adetailer_settings["ad_confidence"] = float(ad_confidence)
        adetailer_settings["ad_denoising_strength"] = float(ad_denoising_strength)
        adetailer_settings["ad_mask_blur"] = int(ad_mask_blur)
        adetailer_settings["ad_dilate_erode"] = int(ad_dilate_erode)
        adetailer_settings["ad_inpaint_only_masked"] = bool(ad_inpaint_only_masked)
        adetailer_settings["ad_inpaint_only_masked_padding"] = int(ad_inpaint_only_masked_padding)

    _generating = True
    try:
        result = comic_engine.run_comic_script(
            script=script,
            output_dir=output_dir,
            cooldown=float(cooldown),
            only_panels=only_panels,
            skip_existing=bool(skip_existing),
            composite=bool(composite),
            num_candidates=int(candidates),
            adetailer_settings=adetailer_settings,
            log=_log,
        )
    except Exception as e:
        _log(f"Error: {e}")
        result = {}
    finally:
        _generating = False

    images = []
    if output_dir and os.path.isdir(output_dir):
        for f in sorted(os.listdir(output_dir)):
            if f.lower().endswith(".png") and not f.endswith(("_bg.png", "_char.png", "_mask.png")):
                images.append(os.path.join(output_dir, f))

    return _get_log(), images


def _assemble_comic_pages(json_str, image_dir, page_width):
    if not json_str.strip():
        return "No script loaded", []

    try:
        script = comic_engine.load_script_from_json(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return f"Script error: {e}", []

    title = script.get("title", "untitled")
    tag = comic_engine.make_title_tag(title)

    if not image_dir.strip():
        image_dir = os.path.join("comics", tag, "pages")

    output_dir = os.path.join("comics", tag, "assembled")

    try:
        pages = assembler.assemble_from_script_data(
            script=script,
            image_dirs=[image_dir],
            output_dir=output_dir,
            page_width=int(page_width),
        )
    except Exception as e:
        return f"Assembly error: {e}", []

    return f"Assembled {len(pages)} pages to {output_dir}", pages


# ═══════════════════════════════════════════════════════════════════════════
# BUILD PAGE HELPER
# ═══════════════════════════════════════════════════════════════════════════

def _add_page_to_script(
    json_str: str,
    layout: str,
    # Panel 1
    scene1: str, shot1: str, dialogue1: str, caption1: str, pos1: str, neg1: str, no_char1: bool, char_key1: str,
    # Panel 2
    scene2: str, shot2: str, dialogue2: str, caption2: str, pos2: str, neg2: str, no_char2: bool, char_key2: str,
    # Panel 3
    scene3: str, shot3: str, dialogue3: str, caption3: str, pos3: str, neg3: str, no_char3: bool, char_key3: str,
    # Panel 4
    scene4: str, shot4: str, dialogue4: str, caption4: str, pos4: str, neg4: str, no_char4: bool, char_key4: str,
) -> tuple:
    """Append a new page to the active comic script JSON.

    Returns (updated_json_str, status_message).
    """
    count = LAYOUT_PANEL_COUNTS.get(layout, 1)

    # Parse or start fresh
    if json_str and json_str.strip():
        try:
            script = json.loads(json_str)
        except json.JSONDecodeError as e:
            return json_str, f"JSON parse error: {e}"
    else:
        script = {
            "title": "Untitled",
            "character": {"lora": "", "activation": "", "weight": 0.8},
            "generation": {},
            "pages": [],
        }

    if "pages" not in script:
        script["pages"] = []

    page_num = len(script["pages"]) + 1

    raw_panels = [
        (scene1, shot1, dialogue1, caption1, pos1, neg1, no_char1, char_key1),
        (scene2, shot2, dialogue2, caption2, pos2, neg2, no_char2, char_key2),
        (scene3, shot3, dialogue3, caption3, pos3, neg3, no_char3, char_key3),
        (scene4, shot4, dialogue4, caption4, pos4, neg4, no_char4, char_key4),
    ]

    panels = []
    for i in range(count):
        scene, shot, dialogue, caption, pos_extra, neg_extra, no_char, char_key = raw_panels[i]
        panel: dict = {
            "id": f"p{page_num:02d}{i + 1:02d}",
            "scene": scene.strip() if scene and scene.strip()
                     else f"PANEL {i + 1} — [describe what the camera sees]",
            "shot": shot or "medium",
        }
        if no_char:
            panel["no_character"] = True
        elif char_key and char_key.strip():
            panel["character"] = char_key.strip()
        if dialogue and dialogue.strip():
            panel["dialogue"] = dialogue.strip()
        if caption and caption.strip():
            panel["caption"] = caption.strip()
        if pos_extra and pos_extra.strip():
            panel["positive_extra"] = pos_extra.strip()
        if neg_extra and neg_extra.strip():
            panel["negative_extra"] = neg_extra.strip()
        panels.append(panel)

    script["pages"].append({"layout": layout, "panels": panels})

    updated = json.dumps(script, indent=2, ensure_ascii=False)
    return updated, f"Added page {page_num} ({layout}, {count} panel{'s' if count > 1 else ''})"


# ═══════════════════════════════════════════════════════════════════════════
# ASSEMBLY SUB-TAB
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_standalone(script_path, image_dir, output_dir, page_width):
    if not script_path or not os.path.isfile(script_path):
        return "Script file not found", []

    if not image_dir.strip():
        image_dir = os.path.dirname(script_path)
    if not output_dir.strip():
        output_dir = os.path.join(os.path.dirname(script_path), "assembled")

    try:
        pages = assembler.assemble_from_script(
            script_path=script_path,
            image_dirs=[image_dir],
            output_dir=output_dir,
            page_width=int(page_width),
        )
    except Exception as e:
        return f"Assembly error: {e}", []

    return f"Assembled {len(pages)} pages to {output_dir}", pages


def _export_pdf(page_gallery):
    if not page_gallery:
        return "No pages to export"
    paths = [p if isinstance(p, str) else p["name"] for p in page_gallery]
    if not paths:
        return "No page images found"
    output_dir = os.path.dirname(paths[0])
    result = assembler.export_pdf(paths, output_dir, "comic_export")
    return f"PDF exported: {result}" if result else "Export failed"


def _export_cbz(page_gallery):
    if not page_gallery:
        return "No pages to export"
    paths = [p if isinstance(p, str) else p["name"] for p in page_gallery]
    if not paths:
        return "No page images found"
    output_dir = os.path.dirname(paths[0])
    result = assembler.export_cbz(paths, output_dir, "comic_export")
    return f"CBZ exported: {result}" if result else "Export failed"


def build_adetailer_block():
    """Build the ADetailer accordion; returns the components in _ad_inputs order."""
    with gr.Accordion("ADetailer", open=False):
        ad_enabled = gr.Checkbox(
            label="Enable ADetailer",
            value=True,
            info="Runs ADetailer face/person inpainting after generation. Disable to skip entirely.",
        )
        ad_model = gr.Dropdown(
            label="Detector model",
            choices=_list_ad_models(),
            value="face_yolov8n.pt",
            interactive=True,
        )
        ad_refresh_models_btn = gr.Button("Refresh models", size="sm")
        ad_prompt = gr.Textbox(
            label="ADetailer prompt",
            placeholder="Leave blank to use the main prompt",
            lines=2,
        )
        ad_negative_prompt = gr.Textbox(
            label="ADetailer negative prompt",
            placeholder="Leave blank to use the main negative prompt",
            lines=2,
        )
        with gr.Row():
            ad_confidence = gr.Slider(
                label="Detection confidence",
                minimum=0.0, maximum=1.0, step=0.01, value=0.3,
            )
            ad_denoising_strength = gr.Slider(
                label="Inpaint denoising strength",
                minimum=0.0, maximum=1.0, step=0.01, value=0.4,
            )
        with gr.Row():
            ad_mask_blur = gr.Slider(
                label="Mask blur",
                minimum=0, maximum=64, step=1, value=4,
            )
            ad_dilate_erode = gr.Slider(
                label="Mask erosion(-) / dilation(+)",
                minimum=-128, maximum=128, step=4, value=4,
            )
        with gr.Row():
            ad_inpaint_only_masked = gr.Checkbox(
                label="Inpaint only masked", value=True,
            )
            ad_inpaint_only_masked_padding = gr.Slider(
                label="Masked padding (px)",
                minimum=0, maximum=256, step=4, value=32,
            )

        ad_refresh_models_btn.click(
            fn=lambda: gr.update(choices=_list_ad_models()),
            outputs=[ad_model],
        )

    return [
        ad_enabled, ad_model, ad_prompt, ad_negative_prompt,
        ad_confidence, ad_denoising_strength,
        ad_mask_blur, ad_dilate_erode,
        ad_inpaint_only_masked, ad_inpaint_only_masked_padding,
    ]


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TAB BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def create_comic_tab():
    """Create the Comic Generator tab with Comic and Assembly sub-tabs."""

    with gr.Blocks(analytics_enabled=False) as tab:
        gr.HTML(
            """<style>
            #comic_panel_gallery .preview .icon-button,
            #comic_page_gallery .preview .icon-button,
            #asm_gallery .preview .icon-button,
            #comic_panel_gallery button[aria-label='Previous'],
            #comic_panel_gallery button[aria-label='Next'],
            #comic_page_gallery button[aria-label='Previous'],
            #comic_page_gallery button[aria-label='Next'],
            #asm_gallery button[aria-label='Previous'],
            #asm_gallery button[aria-label='Next'] {
                pointer-events: auto !important;
                z-index: 50 !important;
                opacity: 1 !important;
            }
            </style>"""
        )
        gr.Markdown("## Comic Generator")

        with gr.Tabs():
            # ── Comic sub-tab ─────────────────────────────────────────────
            with gr.Tab("Comic"):
                with gr.Row():

                    # ── Left column: Script Wizard + Editor ───────────────
                    with gr.Column(scale=2):

                        # ── Integrated Script Wizard ──────────────────────
                        with gr.Accordion("Script Wizard", open=True):
                            gr.Markdown(
                                "Select characters and a format to instantly generate a blank template "
                                "in the editor below. Then edit freely, or paste the JSON into any LLM "
                                "and ask it to fill in the scene, dialogue, and caption fields."
                            )
                            gr.Markdown(
                                "Characters are read from A1111's LoRA card JSONs in `models/Lora/`. "
                                "Edit a card in the WebUI's **LoRA tab → Edit card → Training tags** and save, "
                                "then hit **Refresh Characters**."
                            )
                            with gr.Row():
                                wiz_refresh_btn = gr.Button("Refresh Characters", size="sm")
                                wiz_num_chars = gr.Slider(
                                    label="Number of characters", minimum=1, maximum=4,
                                    step=1, value=1,
                                )
                            wiz_char1 = gr.Dropdown(
                                label="Character 1",
                                choices=_list_characters(),
                                interactive=True,
                            )
                            with gr.Column(visible=False) as wiz_char2_col:
                                wiz_char2 = gr.Dropdown(
                                    label="Character 2",
                                    choices=_list_characters(),
                                    interactive=True,
                                )
                            with gr.Column(visible=False) as wiz_char3_col:
                                wiz_char3 = gr.Dropdown(
                                    label="Character 3",
                                    choices=_list_characters(),
                                    interactive=True,
                                )
                            with gr.Column(visible=False) as wiz_char4_col:
                                wiz_char4 = gr.Dropdown(
                                    label="Character 4",
                                    choices=_list_characters(),
                                    interactive=True,
                                )

                            wiz_format = gr.Radio(
                                label="Script length",
                                choices=[v["label"] for v in FORMATS.values()],
                                value=list(FORMATS.values())[0]["label"],
                            )
                            wiz_apply_btn = gr.Button("Apply Template", variant="secondary", size="sm")

                        # ── Script Editor ─────────────────────────────────
                        gr.Markdown("### Script Editor")
                        script_dd = gr.Dropdown(
                            label="Load script file",
                            choices=_list_script_files(),
                            value=list(_BUILT_IN_EXAMPLES.keys())[0],
                            interactive=True,
                        )
                        refresh_scripts_btn = gr.Button("Refresh file list", size="sm")
                        script_editor = gr.Code(
                            label="Comic Script JSON",
                            language="json",
                            lines=25,
                        )
                        with gr.Row():
                            validate_btn = gr.Button("Validate & Preview")
                            load_file_btn = gr.Button("Load Selected")
                        with gr.Row():
                            save_dir_box = gr.Textbox(
                                label="Save directory",
                                placeholder=str(COMICS_DIR),
                                scale=3,
                            )
                        with gr.Row():
                            save_filename = gr.Textbox(
                                label="Filename",
                                placeholder="my_comic.json",
                                scale=3,
                            )
                            save_script_btn = gr.Button("Save Script", size="sm", scale=1)
                        save_status = gr.Markdown(value="")
                        preview_md = gr.Markdown(label="Preview", value="")

                    # ── Right column: Build Page + Generation Settings ─────
                    with gr.Column(scale=1):

                        # ── Build Page ────────────────────────────────────
                        gr.Markdown("### Build Page")
                        gr.Markdown(
                            "Select a layout, fill in panel details, then click **Add Page** "
                            "to append it to the script JSON on the left."
                        )
                        layout_dd = gr.Dropdown(
                            label="Layout",
                            choices=LAYOUTS,
                            value="three_row",
                            interactive=True,
                        )

                        # Panel groups — shown/hidden based on layout
                        with gr.Accordion("Panel 1", open=True, visible=True) as pg1:
                            p1_no_char = gr.Checkbox(label="No character", value=False)
                            p1_char_key = gr.Textbox(label="Character key", placeholder='e.g. char1 — must match a key in top-level "characters"')
                            p1_scene = gr.Textbox(
                                label="Scene", lines=3,
                                placeholder="Describe what the camera sees — setting, action, lighting",
                            )
                            p1_shot = gr.Dropdown(label="Shot type", choices=SHOT_TYPES, value="medium")
                            p1_dialogue = gr.Textbox(label="Dialogue", placeholder='Speech bubble text (leave blank for none)')
                            p1_caption = gr.Textbox(label="Caption", placeholder='Narrator box text (leave blank for none)')
                            with gr.Row():
                                p1_pos = gr.Textbox(label="Positive extra", placeholder="extra prompt tokens")
                                p1_neg = gr.Textbox(label="Negative extra", placeholder="extra negative tokens")

                        with gr.Accordion("Panel 2", open=True, visible=True) as pg2:
                            p2_no_char = gr.Checkbox(label="No character", value=False)
                            p2_char_key = gr.Textbox(label="Character key", placeholder='e.g. char2 — must match a key in top-level "characters"')
                            p2_scene = gr.Textbox(label="Scene", lines=3, placeholder="Describe the scene")
                            p2_shot = gr.Dropdown(label="Shot type", choices=SHOT_TYPES, value="medium")
                            p2_dialogue = gr.Textbox(label="Dialogue", placeholder="")
                            p2_caption = gr.Textbox(label="Caption", placeholder="")
                            with gr.Row():
                                p2_pos = gr.Textbox(label="Positive extra", placeholder="")
                                p2_neg = gr.Textbox(label="Negative extra", placeholder="")

                        with gr.Accordion("Panel 3", open=True, visible=True) as pg3:
                            p3_no_char = gr.Checkbox(label="No character", value=False)
                            p3_char_key = gr.Textbox(label="Character key", placeholder='e.g. char1 — must match a key in top-level "characters"')
                            p3_scene = gr.Textbox(label="Scene", lines=3, placeholder="Describe the scene")
                            p3_shot = gr.Dropdown(label="Shot type", choices=SHOT_TYPES, value="medium")
                            p3_dialogue = gr.Textbox(label="Dialogue", placeholder="")
                            p3_caption = gr.Textbox(label="Caption", placeholder="")
                            with gr.Row():
                                p3_pos = gr.Textbox(label="Positive extra", placeholder="")
                                p3_neg = gr.Textbox(label="Negative extra", placeholder="")

                        with gr.Accordion("Panel 4", open=True, visible=False) as pg4:
                            p4_no_char = gr.Checkbox(label="No character", value=False)
                            p4_char_key = gr.Textbox(label="Character key", placeholder='e.g. char2 — must match a key in top-level "characters"')
                            p4_scene = gr.Textbox(label="Scene", lines=3, placeholder="Describe the scene")
                            p4_shot = gr.Dropdown(label="Shot type", choices=SHOT_TYPES, value="medium")
                            p4_dialogue = gr.Textbox(label="Dialogue", placeholder="")
                            p4_caption = gr.Textbox(label="Caption", placeholder="")
                            with gr.Row():
                                p4_pos = gr.Textbox(label="Positive extra", placeholder="")
                                p4_neg = gr.Textbox(label="Negative extra", placeholder="")

                        add_page_btn = gr.Button("Add Page", variant="primary")
                        build_status = gr.Markdown(value="")

                        # ── Generation Settings ───────────────────────────
                        with gr.Accordion("Generation Settings", open=False):
                            comic_output_dir = gr.Textbox(
                                label="Output directory",
                                placeholder="Auto from title if empty",
                            )
                            comic_candidates = gr.Slider(
                                label="Candidates per panel", minimum=1, maximum=5,
                                step=1, value=1,
                            )
                            comic_cooldown = gr.Slider(
                                label="Cooldown (sec)", minimum=0, maximum=10,
                                step=0.5, value=2.0,
                            )
                            comic_skip = gr.Checkbox(label="Skip existing panels", value=True)
                            comic_composite = gr.Checkbox(
                                label="Composite mode",
                                value=False,
                                info="Generates BG and character separately, then rembg-extracts the character and pastes onto the BG. Works best with full-body framing on plain-BG character gen. Naively pastes at (0,0) — expect alignment issues.",
                            )
                            comic_only = gr.Textbox(
                                label="Only panels (space-separated IDs)",
                                placeholder="e.g. p0101 p0102 p0103",
                            )
                            comic_page_width = gr.Slider(
                                label="Page width (px)", minimum=1200, maximum=4800,
                                step=100, value=2400,
                            )

                        _ad_inputs = build_adetailer_block()

                        with gr.Row():
                            gen_panels_btn = gr.Button("Generate Panels", variant="primary")
                            assemble_btn = gr.Button("Assemble Pages")
                            stop_comic_btn = gr.Button("Stop", variant="stop")

                comic_log = gr.Textbox(label="Log", lines=10, interactive=False)
                with gr.Row():
                    comic_panel_gallery = gr.Gallery(
                        label="Generated Panels", columns=4, height=400,
                        preview=True, allow_preview=True, object_fit="contain",
                        elem_id="comic_panel_gallery",
                    )
                    comic_page_gallery = gr.Gallery(
                        label="Assembled Pages", columns=2, height=400,
                        preview=True, allow_preview=True, object_fit="contain",
                        elem_id="comic_page_gallery",
                    )

                # ── Wiring: Script Wizard (integrated) ────────────────────

                def _refresh_wiz_chars():
                    choices = _list_characters()
                    return (
                        gr.update(choices=choices),
                        gr.update(choices=choices),
                        gr.update(choices=choices),
                        gr.update(choices=choices),
                    )

                wiz_refresh_btn.click(
                    fn=_refresh_wiz_chars,
                    outputs=[wiz_char1, wiz_char2, wiz_char3, wiz_char4],
                )

                def _on_wiz_num_chars(n):
                    return (
                        gr.update(visible=n >= 2),
                        gr.update(visible=n >= 3),
                        gr.update(visible=n >= 4),
                    )

                wiz_num_chars.change(
                    fn=_on_wiz_num_chars,
                    inputs=[wiz_num_chars],
                    outputs=[wiz_char2_col, wiz_char3_col, wiz_char4_col],
                )

                def _quick_template(c1, c2, c3, c4, fmt):
                    chars = [c for c in [c1, c2, c3, c4] if c]
                    d = DEFAULT_CONFIG.get("defaults", {})
                    return _build_template(
                        chars, fmt,
                        d.get("steps", 27), d.get("cfg_scale", 6.0),
                        d.get("width", 1024), d.get("height", 1280),
                        d.get("sampler", "Euler a"), "", "",
                    )

                _wiz_inputs = [wiz_char1, wiz_char2, wiz_char3, wiz_char4, wiz_format]

                # Auto-populate on format change
                wiz_format.change(
                    fn=_quick_template,
                    inputs=_wiz_inputs,
                    outputs=[script_editor],
                )
                # Also auto-populate when char selections change
                for _wiz_char_dd in [wiz_char1, wiz_char2, wiz_char3, wiz_char4]:
                    _wiz_char_dd.change(
                        fn=_quick_template,
                        inputs=_wiz_inputs,
                        outputs=[script_editor],
                    )
                # Explicit apply button
                wiz_apply_btn.click(
                    fn=_quick_template,
                    inputs=_wiz_inputs,
                    outputs=[script_editor],
                )

                # ── Wiring: Script Editor ─────────────────────────────────

                refresh_scripts_btn.click(
                    fn=lambda: gr.update(choices=_list_script_files()),
                    outputs=[script_dd],
                )
                load_file_btn.click(
                    fn=_load_script_file,
                    inputs=[script_dd],
                    outputs=[script_editor],
                )
                script_dd.change(
                    fn=_load_script_file,
                    inputs=[script_dd],
                    outputs=[script_editor],
                )
                validate_btn.click(
                    fn=_validate_script,
                    inputs=[script_editor],
                    outputs=[preview_md],
                )

                def _save_and_refresh(json_str, filename, save_dir):
                    msg = _save_script_file(json_str, filename, save_dir)
                    new_choices = _list_script_files()
                    return msg, gr.update(choices=new_choices)

                save_script_btn.click(
                    fn=_save_and_refresh,
                    inputs=[script_editor, save_filename, save_dir_box],
                    outputs=[save_status, script_dd],
                )

                # ── Wiring: Build Page ────────────────────────────────────

                def _on_layout_change(layout):
                    count = LAYOUT_PANEL_COUNTS.get(layout, 1)
                    return [gr.update(visible=i < count) for i in range(4)]

                layout_dd.change(
                    fn=_on_layout_change,
                    inputs=[layout_dd],
                    outputs=[pg1, pg2, pg3, pg4],
                )

                _all_panel_fields = [
                    p1_scene, p1_shot, p1_dialogue, p1_caption, p1_pos, p1_neg, p1_no_char, p1_char_key,
                    p2_scene, p2_shot, p2_dialogue, p2_caption, p2_pos, p2_neg, p2_no_char, p2_char_key,
                    p3_scene, p3_shot, p3_dialogue, p3_caption, p3_pos, p3_neg, p3_no_char, p3_char_key,
                    p4_scene, p4_shot, p4_dialogue, p4_caption, p4_pos, p4_neg, p4_no_char, p4_char_key,
                ]

                add_page_btn.click(
                    fn=_add_page_to_script,
                    inputs=[script_editor, layout_dd] + _all_panel_fields,
                    outputs=[script_editor, build_status],
                )

                # ── Wiring: Generation ────────────────────────────────────

                gen_panels_btn.click(
                    fn=_generate_comic_panels,
                    inputs=[
                        script_editor, comic_output_dir, comic_candidates,
                        comic_cooldown, comic_skip, comic_composite, comic_only,
                        *_ad_inputs,
                    ],
                    outputs=[comic_log, comic_panel_gallery],
                )
                assemble_btn.click(
                    fn=_assemble_comic_pages,
                    inputs=[script_editor, comic_output_dir, comic_page_width],
                    outputs=[comic_log, comic_page_gallery],
                )
                stop_comic_btn.click(fn=_stop, outputs=[comic_log])

            # ── Touchup sub-tab ───────────────────────────────────────────
            with gr.Tab("Touchup"):
                from comic.ui_touchup import build_touchup_tab
                build_touchup_tab(build_adetailer_block)

            # ── Assembly sub-tab ──────────────────────────────────────────
            with gr.Tab("Assembly"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Standalone Assembly")
                        gr.Markdown("Re-assemble pages from existing script + images without regenerating.")
                        asm_script = gr.Textbox(
                            label="Script JSON path",
                            placeholder="path/to/script.json",
                        )
                        asm_images = gr.Textbox(
                            label="Image directory",
                            placeholder="Auto from script dir if empty",
                        )
                        asm_output = gr.Textbox(
                            label="Output directory",
                            placeholder="Auto: {script_dir}/assembled/",
                        )
                        asm_width = gr.Slider(
                            label="Page width (px)", minimum=1200, maximum=4800,
                            step=100, value=2400,
                        )
                        with gr.Row():
                            asm_btn = gr.Button("Assemble", variant="primary")
                            pdf_btn = gr.Button("Export PDF")
                            cbz_btn = gr.Button("Export CBZ")

                    with gr.Column():
                        asm_log = gr.Textbox(label="Status", lines=4, interactive=False)
                        asm_gallery = gr.Gallery(
                            label="Assembled Pages", columns=2, height=500,
                            preview=True, allow_preview=True, object_fit="contain",
                            elem_id="asm_gallery",
                        )

                asm_btn.click(
                    fn=_assemble_standalone,
                    inputs=[asm_script, asm_images, asm_output, asm_width],
                    outputs=[asm_log, asm_gallery],
                )
                pdf_btn.click(fn=_export_pdf, inputs=[asm_gallery], outputs=[asm_log])
                cbz_btn.click(fn=_export_cbz, inputs=[asm_gallery], outputs=[asm_log])

    return (tab, "Comic Generator", "comic_generator")
