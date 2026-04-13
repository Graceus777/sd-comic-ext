"""
Script Template Wizard — Comic Generator sub-tab.

Workflow:
  1. Pick 1–4 characters from lora_texts/
  2. Choose a format: Strip, Short Story, or Chapter
  3. Optionally tune generation params
  4. Click "Generate Template" → get a valid JSON scaffold with placeholders
  5. Copy the auto-assembled LLM prompt → paste into ChatGPT / Claude / Gemini
  6. Paste the filled script back into the Comic sub-tab's Script Editor

No A1111 imports — safe to unit-test standalone.
"""
import json
import os
from typing import List, Optional

import gradio as gr

from comic.shared import DEFAULT_CONFIG, LORA_TEXTS_DIR
from comic import strip_engine


# ---------------------------------------------------------------------------
# Format definitions
# ---------------------------------------------------------------------------

FORMATS = {
    "strip": {
        "label": "Strip  (3 panels · 1 page)",
        "pages": [
            ("three_row", 3),
        ],
    },
    "short": {
        "label": "Short Story  (7 panels · 2 pages)",
        "pages": [
            ("t_top",     4),
            ("three_row", 3),
        ],
    },
    "chapter": {
        "label": "Chapter  (15 panels · 5 pages)",
        "pages": [
            ("splash",    1),
            ("l_right",   3),
            ("grid_2x2",  4),
            ("t_bottom",  4),
            ("three_row", 3),
        ],
    },
}

FORMAT_LABELS = {v["label"]: k for k, v in FORMATS.items()}

SAMPLER_CHOICES = ["Euler a", "DPM++ 2M Karras", "DPM++ SDE Karras", "DDIM", "UniPC"]

_DEFAULTS = DEFAULT_CONFIG.get("defaults", {})


# ---------------------------------------------------------------------------
# Pure logic helpers
# ---------------------------------------------------------------------------

def _list_characters() -> list:
    """Return sorted character key list from A1111's LoRA directory."""
    try:
        chars = strip_engine.load_lora_characters()
        return sorted(chars.keys()) if chars else []
    except Exception:
        return []


def _char_search_paths_note() -> str:
    """Return a human-readable note of directories being searched for characters."""
    try:
        from comic.shared import find_lora_dirs
        dirs = find_lora_dirs()
        if dirs:
            paths = "\n".join(f"- `{d}`" for d in dirs)
            return f"**Character search paths:**\n{paths}"
    except Exception:
        pass
    return f"Characters loaded from `{LORA_TEXTS_DIR}`"


def _char_activation(char_key: str) -> str:
    """Return activation text string for a character key, or empty string."""
    if not char_key:
        return ""
    try:
        chars = strip_engine.load_lora_characters()
        data = chars.get(char_key, {})
        return data.get("activation", "") or data.get("activation text", "")
    except Exception:
        return ""


def _char_weight(char_key: str) -> float:
    """Return preferred weight for a character key."""
    if not char_key:
        return 0.8
    try:
        chars = strip_engine.load_lora_characters()
        data = chars.get(char_key, {})
        return float(data.get("weight", data.get("preferred weight", 0.8)))
    except Exception:
        return 0.8


def _build_character_block(char_key: str) -> dict:
    return {
        "lora": char_key,
        "activation": _char_activation(char_key),
        "weight": _char_weight(char_key),
    }


def _panel_placeholder(panel_num: int, page_num: int, character: Optional[str] = None) -> dict:
    pid = f"p{page_num:02d}{panel_num:02d}"
    panel = {
        "id": pid,
        "scene": f"[PANEL {panel_num} — describe what the camera sees: setting, character action, lighting]",
        "dialogue": "[optional dialogue]",
        "caption": "[optional caption]",
        "shot": "medium",
    }
    if character is not None:
        panel["character"] = character
    return panel


def _build_template(
    char_keys: List[Optional[str]],
    format_label: str,
    steps: int,
    cfg: float,
    width: int,
    height: int,
    sampler: str,
    base_positive: str,
    base_negative: str,
) -> str:
    """Return a JSON string of a script template with placeholders.

    char_keys: list of character key strings (None/empty entries are ignored).
    """
    valid_chars = [k for k in char_keys if k]
    fmt_key = FORMAT_LABELS.get(format_label, "strip")
    fmt = FORMATS[fmt_key]

    # Character block
    if len(valid_chars) == 0:
        character = {"lora": "YOUR_LORA_NAME", "activation": "YOUR ACTIVATION TEXT", "weight": 0.8}
        char_field = "character"
    elif len(valid_chars) == 1:
        character = _build_character_block(valid_chars[0])
        char_field = "character"
    else:
        character = {f"char{i+1}": _build_character_block(k) for i, k in enumerate(valid_chars)}
        char_field = "characters"

    # Generation block
    generation = {
        "steps": int(steps),
        "cfg": float(cfg),
        "width": int(width),
        "height": int(height),
        "sampler": sampler,
        "base_positive": base_positive.strip() or _DEFAULTS.get("positive_prompt", "masterpiece, best quality"),
        "base_negative": base_negative.strip() or _DEFAULTS.get("negative_prompt", "(low quality, worst quality:1.4)"),
    }

    # Pages block — in multi-char mode seed each panel with the first character
    # so the script is immediately runnable; the LLM (or user) reassigns as needed
    default_char = list(character.keys())[0] if char_field == "characters" else None
    pages = []
    for page_idx, (layout, panel_count) in enumerate(fmt["pages"], start=1):
        panels = [_panel_placeholder(i + 1, page_idx, character=default_char) for i in range(panel_count)]
        pages.append({"layout": layout, "panels": panels})

    script = {
        "title": "YOUR TITLE HERE",
        char_field: character,
        "generation": generation,
        "pages": pages,
    }
    return json.dumps(script, indent=2, ensure_ascii=False)


def _build_llm_prompt(template_json: str, story_idea: str, char1_key: str) -> str:
    """Return a self-contained copy-paste prompt for any LLM chatbot."""
    activation = _char_activation(char1_key) if char1_key else "your character"
    idea = story_idea.strip() or "[describe your story idea and genre here]"

    header = (
        "You are writing a comic script. Fill in ONLY the scene, dialogue, and caption fields.\n"
        "\n"
        f"CHARACTER: {activation}\n"
        "\n"
        "RULES:\n"
        "• Scenes are visual — describe exactly what the camera sees (pose, location, mood, lighting)\n"
        "• Dialogue goes in speech bubbles — keep each line under 80 characters\n"
        "• Captions are narrator text — short and punchy (under 60 characters)\n"
        "• Set \"dialogue\" or \"caption\" to \"\" for panels that don't need them\n"
        "• Do NOT change any other field (id, shot, layout, lora, generation, etc.)\n"
        "• Return ONLY the completed JSON — no explanations, no markdown fences\n"
        "\n"
        "TEMPLATE:\n"
        f"{template_json}\n"
        "\n"
        f"STORY PROMPT: {idea}"
    )
    return header


# ---------------------------------------------------------------------------
# Gradio UI builder
# ---------------------------------------------------------------------------

def create_wizard_tab_content(script_editor_target):
    """
    Build the Wizard sub-tab UI inside an already-open gr.Tab() context.

    Parameters
    ----------
    script_editor_target : gr.Code
        The script_editor Code component from the Comic sub-tab.
    """
    gr.Markdown(
        "Build a template → paste the LLM prompt into ChatGPT or Claude → "
        "paste the filled script back into the **Comic** tab's Script Editor."
    )

    with gr.Row():
        # ── Left column: inputs ────────────────────────────────────────────
        with gr.Column(scale=2):

            gr.Markdown("### Characters")
            gr.Markdown(
                "Reads A1111 LoRA card JSONs (`activation text`, `preferred weight`, `negative text`). "
                "Edit a card in the WebUI's LoRA panel and save — it will appear here on Refresh."
            )
            char_paths_md = gr.Markdown(value=_char_search_paths_note())
            with gr.Row():
                refresh_chars_btn = gr.Button("Refresh", size="sm")
            num_chars_sl = gr.Slider(
                label="Number of characters", minimum=1, maximum=4, step=1, value=1,
            )
            char1_dd = gr.Dropdown(
                label="Character 1",
                choices=_list_characters(),
                interactive=True,
            )
            char1_preview = gr.Markdown(value="", label="Activation text")
            with gr.Column(visible=False) as char2_col:
                char2_dd = gr.Dropdown(
                    label="Character 2",
                    choices=_list_characters(),
                    interactive=True,
                )
            with gr.Column(visible=False) as char3_col:
                char3_dd = gr.Dropdown(
                    label="Character 3",
                    choices=_list_characters(),
                    interactive=True,
                )
            with gr.Column(visible=False) as char4_col:
                char4_dd = gr.Dropdown(
                    label="Character 4",
                    choices=_list_characters(),
                    interactive=True,
                )

            gr.Markdown("### Format")
            format_radio = gr.Radio(
                label="Script length",
                choices=[v["label"] for v in FORMATS.values()],
                value=list(FORMATS.values())[0]["label"],
            )

            gr.Markdown("### Generation Settings")
            with gr.Accordion("Params (uses extension defaults if blank)", open=False):
                with gr.Row():
                    steps_sl = gr.Slider(
                        label="Steps", minimum=1, maximum=60, step=1,
                        value=_DEFAULTS.get("steps", 28),
                    )
                    cfg_sl = gr.Slider(
                        label="CFG scale", minimum=1.0, maximum=20.0, step=0.5,
                        value=_DEFAULTS.get("cfg_scale", 7.0),
                    )
                with gr.Row():
                    width_sl = gr.Slider(
                        label="Width", minimum=512, maximum=2048, step=64,
                        value=_DEFAULTS.get("width", 768),
                    )
                    height_sl = gr.Slider(
                        label="Height", minimum=512, maximum=2048, step=64,
                        value=_DEFAULTS.get("height", 1024),
                    )
                sampler_dd = gr.Dropdown(
                    label="Sampler",
                    choices=SAMPLER_CHOICES,
                    value=_DEFAULTS.get("sampler", "Euler a"),
                    interactive=True,
                )
                base_pos = gr.Textbox(
                    label="Base positive prompt",
                    placeholder=_DEFAULTS.get("positive_prompt", "masterpiece, best quality"),
                    lines=2,
                )
                base_neg = gr.Textbox(
                    label="Base negative prompt",
                    placeholder=_DEFAULTS.get("negative_prompt", "(low quality, worst quality:1.4)"),
                    lines=2,
                )
                reset_defaults_btn = gr.Button("Reset to extension defaults", size="sm")

            generate_btn = gr.Button("Generate Template", variant="primary")

        # ── Right column: outputs ──────────────────────────────────────────
        with gr.Column(scale=3):

            gr.Markdown("### Generated Template")
            template_code = gr.Code(
                label="Comic Script JSON",
                language="json",
                lines=22,
                interactive=True,
            )
            with gr.Row():
                send_to_editor_btn = gr.Button("Send to Script Editor", variant="secondary")
                clear_btn = gr.Button("Clear", size="sm")

            gr.Markdown(
                "### LLM Prompt\n"
                "Paste the block below into ChatGPT, Claude, or any LLM. "
                "Free tiers can handle 3–5 scripts per session."
            )
            story_idea = gr.Textbox(
                label="Your story idea / genre",
                placeholder="e.g. a rainy afternoon slice-of-life with some playful banter",
                lines=2,
            )
            llm_prompt_box = gr.Textbox(
                label="LLM Prompt  (copy and paste this entire block)",
                lines=14,
                interactive=False,
                show_copy_button=True,
            )

    # ── Wiring ──────────────────────────────────────────────────────────────

    def _refresh_all_chars():
        choices = _list_characters()
        return (
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
        )

    refresh_chars_btn.click(
        fn=_refresh_all_chars,
        outputs=[char1_dd, char2_dd, char3_dd, char4_dd],
    )

    def _on_num_chars(n):
        return (
            gr.update(visible=n >= 2),
            gr.update(visible=n >= 3),
            gr.update(visible=n >= 4),
        )

    num_chars_sl.change(
        fn=_on_num_chars,
        inputs=[num_chars_sl],
        outputs=[char2_col, char3_col, char4_col],
    )

    char1_dd.change(
        fn=lambda k: f"*{_char_activation(k)}*" if _char_activation(k) else "",
        inputs=[char1_dd],
        outputs=[char1_preview],
    )

    def _reset_defaults():
        return (
            _DEFAULTS.get("steps", 28),
            _DEFAULTS.get("cfg_scale", 7.0),
            _DEFAULTS.get("width", 768),
            _DEFAULTS.get("height", 1024),
            _DEFAULTS.get("sampler", "Euler a"),
            "",
            "",
        )

    reset_defaults_btn.click(
        fn=_reset_defaults,
        outputs=[steps_sl, cfg_sl, width_sl, height_sl, sampler_dd, base_pos, base_neg],
    )

    def _on_generate(c1, c2, c3, c4, fmt, steps, cfg, w, h, sampler, bpos, bneg, idea):
        chars = [c for c in [c1, c2, c3, c4] if c]
        tmpl = _build_template(chars, fmt, steps, cfg, w, h, sampler, bpos, bneg)
        prompt = _build_llm_prompt(tmpl, idea, c1)
        return tmpl, prompt

    _template_inputs = [
        char1_dd, char2_dd, char3_dd, char4_dd, format_radio,
        steps_sl, cfg_sl, width_sl, height_sl,
        sampler_dd, base_pos, base_neg,
        story_idea,
    ]

    generate_btn.click(
        fn=_on_generate,
        inputs=_template_inputs,
        outputs=[template_code, llm_prompt_box],
    )

    # Auto-regenerate template when format changes (without needing button click)
    def _auto_template_on_format(c1, c2, c3, c4, fmt, steps, cfg, w, h, sampler, bpos, bneg):
        chars = [c for c in [c1, c2, c3, c4] if c]
        return _build_template(chars, fmt, steps, cfg, w, h, sampler, bpos, bneg)

    format_radio.change(
        fn=_auto_template_on_format,
        inputs=[char1_dd, char2_dd, char3_dd, char4_dd, format_radio,
                steps_sl, cfg_sl, width_sl, height_sl, sampler_dd, base_pos, base_neg],
        outputs=[template_code],
    )

    # Regenerate LLM prompt live when story_idea changes
    story_idea.change(
        fn=lambda tmpl, idea, c1: _build_llm_prompt(tmpl, idea, c1) if tmpl else "",
        inputs=[template_code, story_idea, char1_dd],
        outputs=[llm_prompt_box],
    )

    send_to_editor_btn.click(
        fn=lambda t: t,
        inputs=[template_code],
        outputs=[script_editor_target],
    )

    clear_btn.click(
        fn=lambda: ("", ""),
        outputs=[template_code, llm_prompt_box],
    )

