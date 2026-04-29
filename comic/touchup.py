"""
Touchup backend — per-panel regeneration for comics that were already generated.

Reuses `comic_engine.generate_panel` for txt2img/img2img regen so lora, base
prompts, adetailer, shot tokens all flow through identically to the main
pipeline. Adds an inpaint path via `generation_engine.generate_inpaint`.

Replacement files are written with the canonical `{title_tag}_{panel_id}`
filename pattern (prefixed with a fresh timestamp), which `assembler.
find_script_panel_image` already discovers — no assembly changes needed.

When `overwrite=False` (default), existing files matching the panel are moved
into `{image_dir}/_touchup_backup/` before the new one is generated.
"""
from __future__ import annotations

import copy
import glob as globmod
import os
import shutil
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from comic import comic_engine
from comic import assembler
from comic import generation_engine as gen_engine
from comic.prompt_builder import build_panel_prompt


# -- helpers ---------------------------------------------------------------

def _backup_existing(image_dir: str, title_tag: str, panel_id: str,
                     log: Optional[Callable] = None) -> List[str]:
    """Move any existing files for this panel into _touchup_backup/."""
    backup_dir = os.path.join(image_dir, "_touchup_backup")
    pattern = os.path.join(image_dir, f"*_{title_tag}_{panel_id}*.png")
    files = sorted(globmod.glob(pattern))
    moved: List[str] = []
    if not files:
        return moved
    os.makedirs(backup_dir, exist_ok=True)
    ts = int(time.time())
    for f in files:
        name = os.path.basename(f)
        dest = os.path.join(backup_dir, f"{ts}_{name}")
        try:
            shutil.move(f, dest)
            moved.append(dest)
        except OSError as e:
            if log:
                log(f"  backup failed for {name}: {e}")
    if log and moved:
        log(f"  backed up {len(moved)} file(s) to _touchup_backup/")
    return moved


def _delete_existing(image_dir: str, title_tag: str, panel_id: str,
                     log: Optional[Callable] = None) -> int:
    """Hard-delete any existing files for this panel (overwrite mode)."""
    pattern = os.path.join(image_dir, f"*_{title_tag}_{panel_id}*.png")
    files = sorted(globmod.glob(pattern))
    for f in files:
        try:
            os.remove(f)
        except OSError as e:
            if log:
                log(f"  delete failed for {os.path.basename(f)}: {e}")
    if log and files:
        log(f"  deleted {len(files)} existing file(s)")
    return len(files)


def _find_panel_in_script(script: Dict[str, Any], panel_id: str):
    """Return (page, panel) for a given panel id, or (None, None)."""
    for _, _, panel, page in comic_engine.iter_panels(script):
        if panel.get("id") == panel_id:
            return page, panel
    return None, None


def _resolve_chain_init_path(script: Dict[str, Any], panel: Dict[str, Any],
                             image_dir: str, title_tag: str,
                             log: Optional[Callable] = None) -> Optional[str]:
    """For a panel with `init_from`, find the predecessor's existing image on
    disk so it can be used as the img2img source without regenerating the
    whole chain. Walks the chain up to a depth limit if the immediate
    predecessor is missing on disk.
    """
    visited: List[str] = []
    cur_id = panel.get("init_from")
    while cur_id and cur_id not in visited and len(visited) < 16:
        visited.append(cur_id)
        _, src_panel = _find_panel_in_script(script, cur_id)
        if src_panel is None:
            if log:
                log(f"  chain: predecessor '{cur_id}' not in script")
            return None
        path = assembler.find_script_panel_image(
            src_panel, [image_dir], title_tag,
        )
        if path and os.path.isfile(path):
            return path
        # predecessor has no image yet — try one further back
        cur_id = src_panel.get("init_from")
    return None


# -- public API ------------------------------------------------------------

def touchup_panels(
    script: Dict[str, Any],
    image_dir: str,
    flagged: List[Dict[str, Any]],
    overwrite: bool = False,
    adetailer_settings: Optional[Dict] = None,
    num_candidates: int = 1,
    cooldown: float = 2.0,
    log: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Regenerate flagged panels.

    Each entry in `flagged` is a dict:
        {
            "panel_id": "p0101",
            "prompt_override": "<optional replacement for panel.scene>",
            "init_mode": "txt2img" | "img2img" | "inpaint",
            "init_image": "<path; used for img2img/inpaint>",
            "mask_image": "<path; used for inpaint>",
            "init_denoise": 0.45,
        }
    """
    def _log(msg: str):
        if log:
            log(msg)

    title = script.get("title", "Untitled")
    title_tag = comic_engine.make_title_tag(title)
    os.makedirs(image_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    _log(f"=== Touchup: {title} ({len(flagged)} panel(s)) ===")
    _log(f"Image dir: {os.path.abspath(image_dir)}")
    _log(f"Mode: {'overwrite' if overwrite else 'set-aside backup'}")

    generated = 0
    failed = 0
    new_files: List[str] = []

    for idx, entry in enumerate(flagged):
        if gen_engine._check_interrupted():
            _log("Touchup interrupted by user")
            break

        # Reclaim VRAM before each panel (A1111's UI wrapper would
        # normally do this for us — we bypass it by calling processing
        # directly, so without this multi-panel runs OOM after ~3 panels).
        gen_engine.torch_gc()

        panel_id = entry.get("panel_id") or ""
        if not panel_id:
            continue

        page, src_panel = _find_panel_in_script(script, panel_id)
        if src_panel is None:
            _log(f"[{idx+1}/{len(flagged)}] {panel_id}  SKIP - not in script")
            failed += 1
            continue

        # Work on a deep copy so script stays pristine
        panel = copy.deepcopy(src_panel)

        override = (entry.get("prompt_override") or "").strip()
        if override:
            panel["scene"] = override
            panel["positive_extra"] = ""
            _log(f"[{idx+1}/{len(flagged)}] {panel_id}  override: {override[:80]}")
        else:
            _log(f"[{idx+1}/{len(flagged)}] {panel_id}")

        init_mode = (entry.get("init_mode") or "auto").lower()
        init_path = entry.get("init_image") or ""
        mask_path = entry.get("mask_image") or ""

        # Per-card denoise — only applied when the user is steering the
        # init source explicitly (img2img/inpaint). In Auto mode we defer
        # to the script's init_denoise so per-panel chain values aren't
        # silently overwritten by the slider's default.
        slider_denoise: Optional[float] = None
        if "init_denoise" in entry and entry["init_denoise"] is not None:
            try:
                slider_denoise = float(entry["init_denoise"])
            except (TypeError, ValueError):
                slider_denoise = None
        if slider_denoise is not None and init_mode in ("img2img", "inpaint"):
            panel["init_denoise"] = slider_denoise
            panel["inpaint_denoise"] = slider_denoise

        # Backup or delete existing before generating
        if overwrite:
            _delete_existing(image_dir, title_tag, panel_id, log=_log)
        else:
            # If the current image we'd use for img2img/inpaint is in the
            # image_dir, move it to backup first but remember the backup path
            # so we still have it as the init source.
            pre_backup = _backup_existing(image_dir, title_tag, panel_id, log=_log)
            if init_path and not os.path.isfile(init_path) and pre_backup:
                # caller passed an init_image that was just backed up;
                # resolve to the backed-up copy
                init_path = pre_backup[-1]

        # -- Inpaint path -------------------------------------------------
        if init_mode == "inpaint":
            if not init_path or not os.path.isfile(init_path):
                _log("  SKIP - inpaint needs a valid init image")
                failed += 1
                continue
            if not mask_path or not os.path.isfile(mask_path):
                _log("  SKIP - inpaint needs a valid mask")
                failed += 1
                continue
            ok, files = _run_inpaint(
                script=script, panel=panel,
                init_path=init_path, mask_path=mask_path,
                image_dir=image_dir, title_tag=title_tag,
                timestamp=timestamp,
                adetailer_settings=adetailer_settings,
                log=_log,
            )
            if ok:
                generated += 1
                new_files.extend(files)
            else:
                failed += 1
            if idx < len(flagged) - 1:
                time.sleep(cooldown)
            continue

        # -- txt2img / img2img / auto via generate_panel ------------------
        # For img2img, seed `generated_paths` with the init image so
        # generate_panel's img2img branch picks it up.
        generated_paths: Dict[str, str] = {}
        if init_mode == "img2img" and init_path and os.path.isfile(init_path):
            # Stash under a synthetic key and wire panel.init_from to it
            panel["init_from"] = f"__touchup_src_{panel_id}"
            generated_paths[panel["init_from"]] = init_path
        elif init_mode == "auto" and panel.get("init_from"):
            # Follow the script's chain: use the predecessor's existing
            # image on disk as the init source — no need to regenerate
            # upstream panels.
            chain_src = _resolve_chain_init_path(
                script, panel, image_dir, title_tag, log=_log,
            )
            if chain_src:
                generated_paths[panel["init_from"]] = chain_src
                _log(f"  chain: img2img from '{panel['init_from']}' "
                     f"({os.path.basename(chain_src)})")
            else:
                _log(f"  chain: predecessor image missing — "
                     f"falling back to fresh txt2img")
                panel.pop("init_from", None)
        elif init_mode == "txt2img":
            # Explicit override: ignore script chain
            panel.pop("init_from", None)
        # else: init_mode == "auto" with no init_from in script → plain txt2img

        page_seed = comic_engine.compute_page_seed(title, 0)
        # If the panel specifies a scene_tag, seed hierarchy already handles it.

        ok = comic_engine.generate_panel(
            script, panel, page or {}, image_dir, title_tag, timestamp,
            page_seed=page_seed,
            composite=False,
            num_candidates=int(num_candidates),
            scorer=None,
            generated_paths=generated_paths,
            adetailer_settings=adetailer_settings,
            log=_log,
        )
        if ok:
            generated += 1
            path = generated_paths.get(panel_id)
            if path:
                new_files.append(path)
        else:
            failed += 1

        if idx < len(flagged) - 1:
            time.sleep(cooldown)

    _log(f"=== Touchup finished: {generated} ok, {failed} failed ===")

    return {
        "generated": generated,
        "failed": failed,
        "files": new_files,
        "image_dir": image_dir,
    }


def _strip_backup_prefix(name: str) -> str:
    """Strip the leading '{epoch_ts}_' that _backup_existing prepends.

    Backup names look like "1714312345_20260421-134354_The_Garden_p019.png".
    The first underscore-separated chunk is the backup epoch timestamp.
    """
    parts = name.split("_", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1]
    return name


def restore_last_backup(script: Dict[str, Any], image_dir: str,
                        panel_ids: List[str],
                        log: Optional[Callable] = None) -> int:
    """Move the newest backup of each given panel back into image_dir
    under its original filename. Scans both _touchup_backup/ and
    _removed/ — whichever has the most recent matching file wins.
    Both subfolders use the same `{epoch_ts}_{original_name}` naming."""
    def _log(msg: str):
        if log:
            log(msg)

    if not panel_ids:
        _log("No panels selected for restore")
        return 0

    candidate_dirs = [
        os.path.join(image_dir, "_touchup_backup"),
        os.path.join(image_dir, "_removed"),
    ]
    candidate_dirs = [d for d in candidate_dirs if os.path.isdir(d)]
    if not candidate_dirs:
        _log("No _touchup_backup/ or _removed/ to restore from")
        return 0

    title_tag = comic_engine.make_title_tag(script.get("title", "Untitled"))
    restored = 0

    for pid in panel_ids:
        # Collect matches across both folders, keep the newest by epoch
        # prefix (which is the first chunk of every backed-up filename).
        matches: List[str] = []
        for d in candidate_dirs:
            pattern = os.path.join(d, f"*_{title_tag}_{pid}*.png")
            matches.extend(globmod.glob(pattern))

        if not matches:
            _log(f"  {pid}: no backup found")
            continue

        # Sort by the leading epoch ts in the basename (newest first).
        def _ts_key(path: str) -> int:
            head = os.path.basename(path).split("_", 1)[0]
            return int(head) if head.isdigit() else 0

        matches.sort(key=_ts_key, reverse=True)
        src = matches[0]
        src_folder = os.path.basename(os.path.dirname(src))
        original_name = _strip_backup_prefix(os.path.basename(src))
        dest = os.path.join(image_dir, original_name)

        if os.path.isfile(dest):
            _log(f"  {pid}: SKIP - {original_name} already in image dir")
            continue

        try:
            shutil.move(src, dest)
            restored += 1
            _log(f"  {pid}: restored {original_name} (from {src_folder}/)")
        except OSError as e:
            _log(f"  {pid}: FAIL - {e}")

    _log(f"Restored {restored} panel(s)")
    return restored


def apply_removes(script: Dict[str, Any], image_dir: str,
                  panel_ids: List[str],
                  log: Optional[Callable] = None) -> int:
    """Move images for the given panel ids into _removed/. Assembly then
    treats them as gaps."""
    def _log(msg: str):
        if log:
            log(msg)

    if not panel_ids:
        _log("No panels marked for removal")
        return 0

    title_tag = comic_engine.make_title_tag(script.get("title", "Untitled"))
    removed_dir = os.path.join(image_dir, "_removed")
    os.makedirs(removed_dir, exist_ok=True)
    ts = int(time.time())
    count = 0
    for pid in panel_ids:
        pattern = os.path.join(image_dir, f"*_{title_tag}_{pid}*.png")
        for f in sorted(globmod.glob(pattern)):
            dest = os.path.join(removed_dir, f"{ts}_{os.path.basename(f)}")
            try:
                shutil.move(f, dest)
                count += 1
            except OSError as e:
                _log(f"  move failed for {os.path.basename(f)}: {e}")
    _log(f"Removed {count} file(s) into _removed/")
    return count


# -- inpaint internals -----------------------------------------------------

def _run_inpaint(*, script, panel, init_path: str, mask_path: str,
                 image_dir: str, title_tag: str, timestamp: str,
                 adetailer_settings: Optional[Dict],
                 log: Callable) -> (bool, List[str]):
    """Run a single inpaint pass for the panel."""
    gen = script.get("generation", {})
    character = comic_engine.resolve_panel_character(script, panel)

    base_positive = gen.get("base_positive", "")
    base_negative = gen.get("base_negative", "")
    shot_type = panel.get("shot") or "medium"
    shot_token = comic_engine.get_shot_token(shot_type, 0)

    prompt = build_panel_prompt(character, panel, base_positive,
                                shot_token=shot_token)
    negative = comic_engine._build_negative(
        base_negative, panel.get("negative_extra", ""), character,
    )

    try:
        init_img = Image.open(init_path).convert("RGB")
        mask_img = Image.open(mask_path).convert("L")
    except Exception as e:
        log(f"  FAIL - could not load init/mask: {e}")
        return False, []

    width = panel.get("width") or gen.get("width", init_img.width)
    height = panel.get("height") or gen.get("height", init_img.height)

    panel_id = panel.get("id", "unknown")
    custom_filename = f"{timestamp}_{title_tag}_{panel_id}"

    do_adetailer = character is not None and adetailer_settings is not None

    ok, msg, files, _imgs = gen_engine.generate_inpaint(
        init_image=init_img,
        mask_image=mask_img,
        prompt=prompt,
        negative_prompt=negative,
        steps=gen.get("steps", 27),
        sampler_name=gen.get("sampler", "Euler a"),
        cfg_scale=gen.get("cfg", 6.0),
        width=width,
        height=height,
        seed=panel.get("seed", -1),
        denoising_strength=float(panel.get("inpaint_denoise", 0.55)),
        mask_blur=4,
        inpainting_fill=1,
        inpaint_full_res=True,
        inpaint_full_res_padding=32,
        enable_adetailer=do_adetailer,
        adetailer_settings=adetailer_settings,
        output_dir=image_dir,
        custom_filename=custom_filename,
    )
    status = "OK" if ok else "FAIL"
    log(f"  {status} [inpaint] - {msg}")
    return ok, files or []
