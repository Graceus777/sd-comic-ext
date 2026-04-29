"""
Touchup tab — review every panel of an already-generated comic, flag bad ones,
optionally override the prompt inline, batch-regenerate with the same lora /
base prompt / adetailer pipeline, and save replacements with names that
existing assembly logic picks up automatically.

Entry: user supplies a script JSON path + image directory (mirrors the
Assembly sub-tab's standalone pattern). "Load Panels" populates a dynamic
list of per-panel cards (pre-allocated up to MAX_TOUCHUP_PANELS for Gradio
compatibility; unused cards stay hidden).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from PIL import Image

from comic import comic_engine, assembler
from comic import touchup as touchup_backend


MAX_TOUCHUP_PANELS = 64

STATUS_CHOICES = ["Good", "Flag for touchup", "Remove from slide"]
INIT_MODES = [
    "Auto (follow script chain)",
    "Txt2img (fresh, ignore chain)",
    "Img2img from current",
    "Inpaint (paint mask on image)",
]


def _split_image_value(val: Any) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """Pull (init_image, mask) out of a Gradio sketch-image value.

    With tool="sketch" the value is a dict {"image": PIL, "mask": PIL} when
    the user has painted; otherwise a single PIL/path/None.
    """
    if val is None:
        return None, None
    if isinstance(val, dict):
        img = val.get("image") or val.get("composite")
        msk = val.get("mask")
        if isinstance(img, str) and os.path.isfile(img):
            img = Image.open(img)
        if isinstance(msk, str) and os.path.isfile(msk):
            msk = Image.open(msk)
        return img, msk
    if isinstance(val, Image.Image):
        return val, None
    if isinstance(val, str) and os.path.isfile(val):
        try:
            return Image.open(val), None
        except Exception:
            return None, None
    return None, None


def _mask_is_empty(mask: Image.Image) -> bool:
    """True if the painted mask has no marks."""
    try:
        return mask.convert("L").getbbox() is None
    except Exception:
        return True


def _auto_image_dir(script_path: str, script: Dict[str, Any]) -> str:
    """Best-effort guess of the pages/ directory for a script."""
    title = script.get("title", "untitled")
    tag = comic_engine.make_title_tag(title)
    # 1) Alongside the script file under ./pages
    if script_path:
        here = os.path.dirname(os.path.abspath(script_path))
        cand = os.path.join(here, "pages")
        if os.path.isdir(cand):
            return cand
    # 2) Default comic output layout
    return os.path.join("comics", tag, "pages")


def _load_script_from_path(path: str) -> Dict[str, Any]:
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Script not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return comic_engine.load_script_from_json(f.read())


# -- Load handler ----------------------------------------------------------

def _load_panels(script_path: str, image_dir: str, _state):
    """Populate the per-card components. Returns a flat list of updates."""
    log_lines: List[str] = []

    # Defaults: everything hidden, all fields cleared
    card_updates: List[Any] = []
    state: Dict[str, Any] = {"panels": [], "script_path": "", "image_dir": ""}

    try:
        script = _load_script_from_path(script_path)
    except Exception as e:
        log_lines.append(f"Load failed: {e}")
        for _ in range(MAX_TOUCHUP_PANELS):
            card_updates.extend([
                gr.update(visible=False),  # card group
                gr.update(value=None),     # image
                gr.update(value=""),       # label
                gr.update(value=STATUS_CHOICES[0]),  # status
                gr.update(value=""),       # prompt override
                gr.update(value=INIT_MODES[0]),      # init mode
                gr.update(value=0.55),               # denoise
            ])
        return ["\n".join(log_lines), state, gr.update(value=image_dir)] + card_updates

    resolved_dir = image_dir.strip() or _auto_image_dir(script_path, script)
    title_tag = comic_engine.make_title_tag(script.get("title", "Untitled"))

    panels: List[Tuple[int, int, Dict[str, Any], Dict[str, Any]]] = list(
        comic_engine.iter_panels(script)
    )
    log_lines.append(f"Loaded '{script.get('title', '?')}' - {len(panels)} panel(s)")
    log_lines.append(f"Scanning images in: {os.path.abspath(resolved_dir)}")

    if len(panels) > MAX_TOUCHUP_PANELS:
        log_lines.append(
            f"WARNING: only the first {MAX_TOUCHUP_PANELS} panels are shown "
            f"(script has {len(panels)})"
        )

    state["panels"] = [
        {"panel_id": p.get("id", ""), "page_index": pi, "panel_index": qi}
        for pi, qi, p, _ in panels
    ]
    state["script_path"] = script_path
    state["image_dir"] = resolved_dir

    image_dirs = [resolved_dir] if os.path.isdir(resolved_dir) else []

    for i in range(MAX_TOUCHUP_PANELS):
        if i < len(panels):
            pi, qi, panel, _page = panels[i]
            panel_id = panel.get("id", f"p{pi+1}{qi+1}")
            img_path = assembler.find_script_panel_image(
                panel, image_dirs, title_tag,
            )
            scene = panel.get("scene", "")[:60]
            label = (
                f"**{panel_id}** — page {pi+1}, panel {qi+1}"
                + (f"  \n_{scene}_" if scene else "")
            )
            card_updates.extend([
                gr.update(visible=True),
                gr.update(value=img_path if img_path and os.path.isfile(img_path) else None),
                gr.update(value=label),
                gr.update(value=STATUS_CHOICES[0]),
                gr.update(value=""),
                gr.update(value=INIT_MODES[0]),
                gr.update(value=0.55),
            ])
        else:
            card_updates.extend([
                gr.update(visible=False),
                gr.update(value=None),
                gr.update(value=""),
                gr.update(value=STATUS_CHOICES[0]),
                gr.update(value=""),
                gr.update(value=INIT_MODES[0]),
                gr.update(value=0.55),
            ])

    return ["\n".join(log_lines), state, gr.update(value=resolved_dir)] + card_updates


# -- Bulk status ops -------------------------------------------------------

def _set_all_status(value: str, _state):
    return [gr.update(value=value) for _ in range(MAX_TOUCHUP_PANELS)]


def _invert_status(_state, *statuses):
    out = []
    for s in statuses:
        if s == "Flag for touchup":
            out.append(gr.update(value="Good"))
        elif s == "Good":
            out.append(gr.update(value="Flag for touchup"))
        else:
            out.append(gr.update(value=s))
    return out


# -- Regenerate ------------------------------------------------------------

def _regen(state, overwrite, candidates, cooldown,
           ad_enabled, ad_model, ad_prompt, ad_negative_prompt,
           ad_confidence, ad_denoising_strength,
           ad_mask_blur, ad_dilate_erode,
           ad_inpaint_only_masked, ad_inpaint_only_masked_padding,
           *card_values):
    """
    card_values is a flat tuple of (status, prompt_override, init_mode, image,
    denoise) for each of MAX_TOUCHUP_PANELS. (image is the current gr.Image
    value supplied back to use as img2img/inpaint source.)
    """
    log_lines: List[str] = []
    if not state or not state.get("script_path"):
        return "Load a script first.", []

    try:
        script = _load_script_from_path(state["script_path"])
    except Exception as e:
        return f"Script reload failed: {e}", []

    image_dir = state.get("image_dir") or ""
    if not image_dir:
        return "Missing image directory.", []

    per_card = 5  # status, prompt_override, init_mode, current_image, denoise
    panels = state.get("panels", [])
    flagged: List[Dict[str, Any]] = []
    skip_msgs: List[str] = []
    temp_dir = tempfile.mkdtemp(prefix="comic_touchup_")

    for i, meta in enumerate(panels):
        if i >= MAX_TOUCHUP_PANELS:
            break
        base = i * per_card
        status = card_values[base]
        prompt_override = card_values[base + 1]
        init_mode_label = card_values[base + 2]
        current_image = card_values[base + 3]
        denoise_val = card_values[base + 4]

        if status != "Flag for touchup":
            continue

        init_mode = {
            "Auto (follow script chain)": "auto",
            "Txt2img (fresh, ignore chain)": "txt2img",
            "Img2img from current": "img2img",
            "Inpaint (paint mask on image)": "inpaint",
        }.get(init_mode_label, "auto")

        init_pil, mask_pil = _split_image_value(current_image)
        panel_id = meta["panel_id"]

        # Validate inpaint pre-conditions early so the user gets a clear log
        if init_mode == "inpaint":
            if init_pil is None:
                skip_msgs.append(
                    f"{panel_id}: SKIP - inpaint needs a panel image (none loaded)"
                )
                continue
            if mask_pil is None or _mask_is_empty(mask_pil):
                skip_msgs.append(
                    f"{panel_id}: SKIP - inpaint needs a painted mask "
                    f"(draw on the image, then re-run)"
                )
                continue

        # Persist init/mask to temp files so the backend can re-open them
        init_path = ""
        mask_path = ""
        if init_pil is not None and init_mode in ("img2img", "inpaint"):
            init_path = os.path.join(temp_dir, f"init_{panel_id}.png")
            try:
                init_pil.convert("RGB").save(init_path)
            except Exception as e:
                skip_msgs.append(f"{panel_id}: SKIP - could not stage init image: {e}")
                continue
        if mask_pil is not None and init_mode == "inpaint":
            mask_path = os.path.join(temp_dir, f"mask_{panel_id}.png")
            try:
                mask_pil.convert("L").save(mask_path)
            except Exception as e:
                skip_msgs.append(f"{panel_id}: SKIP - could not stage mask: {e}")
                continue

        flagged.append({
            "panel_id": panel_id,
            "prompt_override": prompt_override or "",
            "init_mode": init_mode,
            "init_image": init_path,
            "mask_image": mask_path,
            "init_denoise": float(denoise_val) if denoise_val is not None else 0.55,
        })

    if not flagged:
        shutil.rmtree(temp_dir, ignore_errors=True)
        msg = "No panels flagged for touchup."
        if skip_msgs:
            msg = "\n".join(skip_msgs) + "\n" + msg
        return msg, []

    adetailer_settings = None
    if ad_enabled:
        adetailer_settings = {"ad_model": ad_model or "face_yolov8n.pt"}
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

    def _log(msg: str):
        log_lines.append(msg)

    for m in skip_msgs:
        _log(m)

    try:
        result = touchup_backend.touchup_panels(
            script=script,
            image_dir=image_dir,
            flagged=flagged,
            overwrite=bool(overwrite),
            adetailer_settings=adetailer_settings,
            num_candidates=int(candidates),
            cooldown=float(cooldown),
            log=_log,
        )
    except Exception as e:
        _log(f"Error: {e}")
        result = {"files": []}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return "\n".join(log_lines), result.get("files", [])


# -- Restore from backup ---------------------------------------------------

def _restore_backups(state, *statuses):
    """Restore the most recent _touchup_backup/ entry for every flagged
    panel — meant for recovering after a partially failed touchup run."""
    log_lines: List[str] = []
    if not state or not state.get("script_path"):
        return "Load a script first."
    try:
        script = _load_script_from_path(state["script_path"])
    except Exception as e:
        return f"Script reload failed: {e}"

    panels = state.get("panels", [])
    panel_ids: List[str] = []
    for i, meta in enumerate(panels):
        if i >= MAX_TOUCHUP_PANELS:
            break
        if statuses[i] == "Flag for touchup":
            panel_ids.append(meta["panel_id"])

    if not panel_ids:
        return ("Flag the panels you want to restore from _touchup_backup/, "
                "then click Restore.")

    image_dir = state.get("image_dir") or ""
    if not image_dir:
        return "Missing image directory."

    touchup_backend.restore_last_backup(
        script, image_dir, panel_ids,
        log=lambda m: log_lines.append(m),
    )
    return "\n".join(log_lines)


# -- Apply Removes ---------------------------------------------------------

def _apply_removes(state, *statuses):
    log_lines: List[str] = []
    if not state or not state.get("script_path"):
        return "Load a script first."
    try:
        script = _load_script_from_path(state["script_path"])
    except Exception as e:
        return f"Script reload failed: {e}"

    panels = state.get("panels", [])
    to_remove: List[str] = []
    for i, meta in enumerate(panels):
        if i >= MAX_TOUCHUP_PANELS:
            break
        if statuses[i] == "Remove from slide":
            to_remove.append(meta["panel_id"])

    if not to_remove:
        return "No panels marked for removal."

    image_dir = state.get("image_dir") or ""
    touchup_backend.apply_removes(
        script, image_dir, to_remove, log=lambda m: log_lines.append(m),
    )
    return "\n".join(log_lines)


# -- Re-assemble -----------------------------------------------------------

def _reassemble(state, page_width):
    from comic.ui_comic import _assemble_comic_pages
    if not state or not state.get("script_path"):
        return "Load a script first.", []
    try:
        with open(state["script_path"], "r", encoding="utf-8") as f:
            json_str = f.read()
    except Exception as e:
        return f"Script read failed: {e}", []
    return _assemble_comic_pages(json_str, state.get("image_dir", ""), page_width)


# -- Tab builder -----------------------------------------------------------

def build_touchup_tab(build_adetailer_block):
    """Build the Touchup sub-tab. `build_adetailer_block` is injected to
    avoid circular imports with ui_comic."""
    tu_state = gr.State({"panels": [], "script_path": "", "image_dir": ""})

    with gr.Row():
        tu_script = gr.Textbox(
            label="Script JSON path",
            placeholder="path/to/script.json",
        )
        tu_images = gr.Textbox(
            label="Image directory",
            placeholder="Auto: {script_dir}/pages/ or comics/{title_tag}/pages/",
        )
    with gr.Row():
        tu_load_btn = gr.Button("Load Panels", variant="primary")
        tu_flag_all_btn = gr.Button("Flag all")
        tu_clear_all_btn = gr.Button("Clear flags")
        tu_invert_btn = gr.Button("Invert flags")

    # Dynamic card list — all pre-allocated, toggled via visibility
    card_groups: List[gr.Group] = []
    card_images: List[gr.Image] = []
    card_labels: List[gr.Markdown] = []
    card_statuses: List[gr.Radio] = []
    card_overrides: List[gr.Textbox] = []
    card_init_modes: List[gr.Dropdown] = []
    card_denoises: List[gr.Slider] = []

    with gr.Column():
        # Two-column grid of cards
        for i in range(MAX_TOUCHUP_PANELS):
            with gr.Group(visible=False) as g:
                with gr.Row():
                    with gr.Column(scale=1):
                        img = gr.Image(
                            label=f"Panel {i+1}",
                            type="pil",
                            tool="sketch",
                            source="upload",
                            height=640,
                            interactive=True,
                        )
                    with gr.Column(scale=2):
                        lbl = gr.Markdown(value="")
                        status = gr.Radio(
                            choices=STATUS_CHOICES,
                            value=STATUS_CHOICES[0],
                            label="Status",
                        )
                        override = gr.Textbox(
                            label="Prompt override (optional)",
                            placeholder="Leave blank to use the script's prompt as-is",
                            lines=2,
                        )
                        init_mode = gr.Dropdown(
                            label="Init mode",
                            choices=INIT_MODES,
                            value=INIT_MODES[0],
                            info="Inpaint: paint over the area to regenerate, then flag and run.",
                        )
                        denoise = gr.Slider(
                            label="Denoising strength (img2img / inpaint)",
                            minimum=0.0, maximum=1.0, step=0.01, value=0.55,
                            info="Ignored for Txt2img.",
                        )
            card_groups.append(g)
            card_images.append(img)
            card_labels.append(lbl)
            card_statuses.append(status)
            card_overrides.append(override)
            card_init_modes.append(init_mode)
            card_denoises.append(denoise)

    # Ordered list of per-card components used in load output:
    #   group, image, label, status, override, init_mode, denoise
    load_outputs: List[Any] = []
    for i in range(MAX_TOUCHUP_PANELS):
        load_outputs.extend([
            card_groups[i], card_images[i], card_labels[i],
            card_statuses[i], card_overrides[i], card_init_modes[i],
            card_denoises[i],
        ])

    with gr.Accordion("Touchup settings", open=False):
        tu_overwrite = gr.Checkbox(
            label="Overwrite in place (destructive)",
            value=False,
            info="If off (recommended), old images move to _touchup_backup/ before the new one is generated.",
        )
        tu_candidates = gr.Slider(
            label="Candidates per panel",
            minimum=1, maximum=5, step=1, value=1,
        )
        tu_cooldown = gr.Slider(
            label="Cooldown (sec)",
            minimum=0, maximum=10, step=0.5, value=2.0,
        )
        tu_page_width = gr.Slider(
            label="Page width (px) — for re-assembly",
            minimum=1200, maximum=4800, step=100, value=2400,
        )

    tu_ad_inputs = build_adetailer_block()

    with gr.Row():
        tu_regen_btn = gr.Button("Touch Up Flagged Panels", variant="primary")
        tu_restore_btn = gr.Button(
            "Restore Backup (flagged)",
            elem_id="tu_restore_btn",
        )
        tu_apply_removes_btn = gr.Button("Apply Removes")
        tu_assemble_btn = gr.Button("Re-assemble Pages")
        tu_stop_btn = gr.Button("Stop", variant="stop")

    tu_log = gr.Textbox(label="Log", lines=8, interactive=False)
    tu_gallery = gr.Gallery(
        label="Touchup Results", columns=4, height=300,
        preview=True, allow_preview=True, object_fit="contain",
        elem_id="tu_gallery",
    )

    # -- Wiring --

    tu_load_btn.click(
        fn=_load_panels,
        inputs=[tu_script, tu_images, tu_state],
        outputs=[tu_log, tu_state, tu_images] + load_outputs,
    )

    tu_flag_all_btn.click(
        fn=lambda s: _set_all_status("Flag for touchup", s),
        inputs=[tu_state],
        outputs=card_statuses,
    )
    tu_clear_all_btn.click(
        fn=lambda s: _set_all_status("Good", s),
        inputs=[tu_state],
        outputs=card_statuses,
    )
    tu_invert_btn.click(
        fn=_invert_status,
        inputs=[tu_state] + card_statuses,
        outputs=card_statuses,
    )

    # Regenerate: flatten per-card inputs in order
    regen_card_inputs: List[Any] = []
    for i in range(MAX_TOUCHUP_PANELS):
        regen_card_inputs.extend([
            card_statuses[i], card_overrides[i],
            card_init_modes[i], card_images[i],
            card_denoises[i],
        ])

    tu_regen_btn.click(
        fn=_regen,
        inputs=[
            tu_state, tu_overwrite, tu_candidates, tu_cooldown,
            *tu_ad_inputs,
        ] + regen_card_inputs,
        outputs=[tu_log, tu_gallery],
    )

    tu_restore_btn.click(
        fn=_restore_backups,
        inputs=[tu_state] + card_statuses,
        outputs=[tu_log],
    )

    tu_apply_removes_btn.click(
        fn=_apply_removes,
        inputs=[tu_state] + card_statuses,
        outputs=[tu_log],
    )

    tu_assemble_btn.click(
        fn=_reassemble,
        inputs=[tu_state, tu_page_width],
        outputs=[tu_log, tu_gallery],
    )

    def _stop():
        try:
            from modules import shared
            shared.state.interrupted = True
            return "Interrupt requested..."
        except Exception:
            return "Could not send interrupt signal"

    tu_stop_btn.click(fn=_stop, outputs=[tu_log])
