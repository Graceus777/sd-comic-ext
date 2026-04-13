"""
Comic script engine for generating panels within the A1111 extension.

Ported from generate_comic.py — replaces HTTP API calls with direct
modules.processing calls via generation_engine.py.

Features:
  - Shot type inference with diction variants
  - Multi-candidate generation with scoring
  - Scene-based seeding for consistent lighting
  - img2img chaining for sequential panel consistency
  - Composite mode (bg + character + rembg)
  - Hierarchical seed: panel > scene > page > random
"""
import os
import re
import time
import shutil
import glob as globmod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from PIL import Image

from . import generation_engine as gen_engine
from .prompt_builder import (
    LARGE_SLOT_LAYOUTS,
    build_panel_prompt,
    compute_page_seed,
    compute_scene_seed,
    get_shot_token,
    infer_shot_type,
    panel_needs_auto_hires,
    validate_camera_continuity,
)
from .panel_scorer import PanelScorer


# -- script parsing ---------------------------------------------------------

def load_script(path: str) -> Dict[str, Any]:
    """Load and validate a comic script JSON file."""
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "pages" not in data:
        raise ValueError("Comic script must contain a 'pages' array")
    if "character" not in data and "characters" not in data:
        raise ValueError("Comic script must contain a 'character' or 'characters' object")
    return data


def load_script_from_json(json_str: str) -> Dict[str, Any]:
    """Load and validate a comic script from a JSON string."""
    import json
    data = json.loads(json_str)
    if "pages" not in data:
        raise ValueError("Comic script must contain a 'pages' array")
    if "character" not in data and "characters" not in data:
        raise ValueError("Comic script must contain a 'character' or 'characters' object")
    return data


def iter_panels(script: Dict[str, Any]):
    """Yield (page_index, panel_index, panel_dict, page_dict) for every panel."""
    for pi, page in enumerate(script.get("pages", [])):
        for qi, panel in enumerate(page.get("panels", [])):
            yield pi, qi, panel, page


def collect_panel_ids(script: Dict[str, Any]) -> List[str]:
    """Return a list of all panel IDs in document order."""
    return [panel["id"] for _, _, panel, _ in iter_panels(script) if "id" in panel]


# -- filename helpers -------------------------------------------------------

def make_title_tag(title: str) -> str:
    """Sanitise a title string into a safe filename fragment."""
    return re.sub(r"[^\w]", "_", title)[:20]


def panel_already_generated(output_dir: str, title_tag: str, panel_id: str) -> bool:
    """Check whether at least one output image already exists for a panel."""
    pattern = os.path.join(output_dir, f"*_{title_tag}_{panel_id}*.png")
    return len(globmod.glob(pattern)) > 0


# -- character resolution ---------------------------------------------------

def resolve_panel_character(
    script: Dict[str, Any],
    panel: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Resolve the character config for a panel.

    Supports two modes:
      - Single character: script has "character" (dict) — used for all panels
      - Multi character: script has "characters" (dict of dicts) — per-panel
        selection via panel["character"] key name

    Returns None for no_character panels or when no character applies.
    """
    if panel.get("no_character", False):
        return None

    characters = script.get("characters")
    if characters:
        char_key = panel.get("character")
        if char_key and char_key in characters:
            return characters[char_key]
        return None

    return script.get("character")


# -- compositing (bg + character + rembg) -----------------------------------

def _remove_bg(image: Image.Image, alpha_threshold: int = 50) -> Image.Image:
    """Remove background using rembg. Returns RGBA with thresholded alpha."""
    from rembg import remove
    rgba = remove(image)
    alpha = rgba.split()[3]
    alpha = alpha.point(lambda x: 255 if x > alpha_threshold else 0)
    rgba.putalpha(alpha)
    return rgba


def _build_negative(
    base_negative: str,
    panel_negative_extra: str,
    character: Optional[Dict[str, Any]],
) -> str:
    """Assemble the full negative prompt.

    Order: character LoRA negative → panel extra → base negative.
    """
    parts = []
    if character and character.get("negative"):
        parts.append(character["negative"])
    if panel_negative_extra:
        parts.append(panel_negative_extra)
    if base_negative:
        parts.append(base_negative)
    return ", ".join(p for p in parts if p)


def generate_panel_composite(
    script: Dict[str, Any],
    panel: Dict[str, Any],
    page: Dict[str, Any],
    character: Dict[str, Any],
    prompt: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    sampler: str,
    seed: int,
    do_hires: bool,
    hr_denoise: float,
    output_dir: str,
    custom_filename: str,
    adetailer_settings: Optional[Dict] = None,
    log: Optional[Callable] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Generate a panel by compositing a character onto a separate background.

    Pipeline:
      1. Generate background (scene prompt, no character)
      2. Generate character (full prompt with LoRA + simple background)
      3. rembg to extract character mask
      4. Composite character onto background

    Returns (success, output_path).
    """
    def _log(msg):
        if log:
            log(msg)

    gen = script.get("generation", {})
    base_positive = gen.get("base_positive", "")
    base_negative = gen.get("base_negative", "")

    # --- Step 1: Background ---
    bg_scene = panel.get("bg_scene", "")
    if not bg_scene:
        raw = panel.get("scene", "")
        person_words = re.compile(
            r'\b(?:she|her|his|he|him|herself|himself|'
            r'eyes?|gaze|expression|smile|smirk|frown|lips?|face|portrait|'
            r'hair|shoulders?|arms?|hands?|fingers?|legs?|'
            r'navel|bare|chest|waist|hips?|'
            r'standing|sitting|leaning|crouching|kneeling|walking|turning|'
            r'looking|watching|surveying|posing|'
            r'snake tail|tail|scales|'
            r'wine glass in hand|holding|wearing|dressed|'
            r'confident|elegant|dangerous|amused|composed|'
            r'mask(?:ed)?|jewelry|earring|necklace|choker|'
            r'cape|outfit|costume)\b',
            re.IGNORECASE,
        )
        bg_phrases = []
        for phrase in raw.split(','):
            phrase = phrase.strip()
            if phrase and not person_words.search(phrase):
                bg_phrases.append(phrase)
        bg_scene = ', '.join(bg_phrases) if bg_phrases else raw

    bg_panel = dict(panel)
    bg_panel["scene"] = bg_scene
    bg_panel["no_character"] = True
    bg_prompt = build_panel_prompt(None, bg_panel, base_positive)
    bg_negative = f"1girl, solo, person, human, figure, face, body, {base_negative}" if base_negative else \
                  "1girl, solo, person, human, figure, face, body"

    _log("[composite] generating background...")
    ok, msg, files, images = gen_engine.generate_txt2img(
        prompt=bg_prompt,
        negative_prompt=bg_negative,
        steps=steps,
        sampler_name=sampler,
        cfg_scale=cfg,
        width=width,
        height=height,
        enable_hr=do_hires,
        hr_scale=1.5,
        hr_upscaler="Latent",
        denoising_strength=hr_denoise,
        seed=seed,
        batch_size=1,
        output_dir=output_dir,
        custom_filename=f"{custom_filename}_bg",
    )
    if not ok or not images:
        _log(f"[composite] BG failed: {msg}")
        return False, None
    bg_img = images[0].convert("RGB")

    # --- Step 2: Character ---
    char_prompt = prompt + ", simple background, plain background, solid color background"

    _log("[composite] generating character...")
    ok, msg, files, images = gen_engine.generate_txt2img(
        prompt=char_prompt,
        negative_prompt=negative,
        steps=steps,
        sampler_name=sampler,
        cfg_scale=cfg,
        width=width,
        height=height,
        enable_hr=do_hires,
        hr_scale=1.5,
        hr_upscaler="Latent",
        denoising_strength=hr_denoise,
        enable_adetailer=True,
        adetailer_settings=adetailer_settings,
        seed=seed + 1 if seed != -1 else -1,
        batch_size=1,
        output_dir=output_dir,
        custom_filename=f"{custom_filename}_char",
    )
    if not ok or not images:
        _log(f"[composite] CHAR failed: {msg}")
        return False, None
    char_img = images[0].convert("RGB")

    # --- Step 3: rembg ---
    _log("[composite] removing background...")
    try:
        char_rgba = _remove_bg(char_img)
    except Exception as e:
        _log(f"[composite] rembg error: {e}")
        return False, None

    # --- Step 4: Composite ---
    _log("[composite] compositing...")
    if bg_img.size != char_rgba.size:
        char_rgba = char_rgba.resize(bg_img.size, Image.LANCZOS)

    composite_img = bg_img.copy()
    composite_img.paste(char_rgba, (0, 0), char_rgba.split()[3])

    # Save intermediates + final
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    mask_path = os.path.join(output_dir, f"{ts}_{custom_filename}_mask.png")
    final_path = os.path.join(output_dir, f"{ts}_{custom_filename}.png")

    char_rgba.split()[3].save(mask_path)
    composite_img.save(final_path)

    _log("OK - Saved composite + intermediates")
    return True, os.path.abspath(final_path).replace("\\", "/")


# -- img2img chaining -------------------------------------------------------

def generate_panel_img2img(
    prompt: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    sampler: str,
    seed: int,
    do_adetailer: bool,
    init_image_path: str,
    denoise_strength: float,
    output_dir: str,
    custom_filename: str,
    adetailer_settings: Optional[Dict] = None,
    log: Optional[Callable] = None,
) -> Tuple[bool, List[str]]:
    """Generate a panel using img2img from a previous panel's output."""
    def _log(msg):
        if log:
            log(msg)

    img = Image.open(init_image_path).convert("RGB")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)

    ok, msg, files, _images = gen_engine.generate_img2img(
        init_image=img,
        prompt=prompt,
        negative_prompt=negative,
        steps=steps,
        sampler_name=sampler,
        cfg_scale=cfg,
        width=width,
        height=height,
        seed=seed,
        batch_size=1,
        denoising_strength=denoise_strength,
        enable_adetailer=do_adetailer,
        adetailer_settings=adetailer_settings,
        output_dir=output_dir,
        custom_filename=custom_filename,
    )

    src_name = os.path.basename(init_image_path)
    status = "OK" if ok else "FAIL"
    _log(f"{status} [img2img from {src_name}, denoise={denoise_strength}] - {msg}")
    return ok, files


# -- multi-candidate generation ---------------------------------------------

def generate_panel_candidates(
    script: Dict[str, Any],
    panel: Dict[str, Any],
    page: Dict[str, Any],
    output_dir: str,
    title_tag: str,
    timestamp: str,
    base_seed: int,
    num_candidates: int,
    scorer: Optional[PanelScorer],
    init_image_path: Optional[str] = None,
    adetailer_settings: Optional[Dict] = None,
    log: Optional[Callable] = None,
) -> Tuple[bool, List[str]]:
    """Generate N candidates with seed/diction variation, score, select best."""
    def _log(msg):
        if log:
            log(msg)

    gen = script.get("generation", {})
    character = resolve_panel_character(script, panel)

    base_positive = gen.get("base_positive", "")
    base_negative = gen.get("base_negative", "")

    negative = _build_negative(base_negative, panel.get("negative_extra", ""), character)
    if character is None:
        no_person = "1girl, solo, person, human, figure"
        negative = f"{no_person}, {negative}" if negative else no_person

    width = panel.get("width") or gen.get("width", 1024)
    height = panel.get("height") or gen.get("height", 1280)
    do_hires = panel.get("hires", False)
    if not do_hires and panel_needs_auto_hires(panel, page):
        do_hires = True
    hr_denoise = panel.get("hr_denoise", 0.5)
    steps = gen.get("steps", 27)
    cfg = gen.get("cfg", 6.0)
    sampler = gen.get("sampler", "Euler a")
    if character is None:
        do_adetailer = False
    elif adetailer_settings is not None:
        do_adetailer = True
    else:
        do_adetailer = gen.get("adetailer", True)

    panel_id = panel.get("id", "unknown")
    custom_filename = f"{title_tag}_{panel_id}"
    expects_face = character is not None

    shot_type = panel.get("shot") or infer_shot_type(
        panel.get("scene", ""), panel.get("positive_extra", ""),
        panel.get("no_character", False),
    )

    cand_dir = os.path.join(output_dir, "_candidates", panel_id)
    os.makedirs(cand_dir, exist_ok=True)

    use_img2img = init_image_path is not None and os.path.isfile(init_image_path)
    init_denoise = panel.get("init_denoise", 0.45)

    candidate_paths: List[str] = []

    for ci in range(num_candidates):
        # Check for interrupt
        if gen_engine._check_interrupted():
            _log("Interrupted by user")
            break

        # Spread seeds by large prime stride
        if base_seed != -1:
            seed = (base_seed + ci * 7919) % (2**32)
        else:
            seed = -1

        shot_token = get_shot_token(shot_type, ci)
        prompt = build_panel_prompt(character, panel, base_positive, shot_token=shot_token)

        cand_name = f"{timestamp}_{custom_filename}_c{ci+1:02d}"

        if use_img2img:
            ok, files = generate_panel_img2img(
                prompt, negative, width, height,
                steps, cfg, sampler, seed, do_adetailer,
                init_image_path, init_denoise,
                cand_dir, cand_name,
                adetailer_settings=adetailer_settings, log=log,
            )
        else:
            ok, msg, files, _imgs = gen_engine.generate_txt2img(
                prompt=prompt,
                negative_prompt=negative,
                steps=steps, sampler_name=sampler, cfg_scale=cfg,
                width=width, height=height,
                enable_hr=do_hires, hr_scale=1.5, hr_upscaler="Latent",
                denoising_strength=hr_denoise,
                enable_adetailer=do_adetailer,
                adetailer_settings=adetailer_settings,
                seed=seed, batch_size=1,
                output_dir=cand_dir, custom_filename=cand_name,
            )

        if ok and files:
            candidate_paths.append(files[0])
            _log(f"candidate {ci+1}/{num_candidates}: {shot_type}[{ci}] seed={seed}")
        else:
            _log(f"candidate {ci+1}/{num_candidates}: FAILED")

        if ci < num_candidates - 1:
            time.sleep(0.5)

    if not candidate_paths:
        return False, []

    # Score and select
    if scorer and len(candidate_paths) > 1:
        prompt_for_score = build_panel_prompt(character, panel, base_positive)
        best_path, details = scorer.select_best(
            candidate_paths, prompt_for_score, expects_face,
        )
        for fname, info in details.items():
            marker = " <<<" if fname in best_path else ""
            _log(f"score {fname}: {info['total']:.3f} "
                 f"(tech={info.get('technical', 0):.2f} "
                 f"aes={info.get('aesthetic', 0):.2f} "
                 f"content={info.get('content', 'n/a')}){marker}")
    else:
        best_path = candidate_paths[0]

    # Copy winner to main output dir
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    winner_filename = f"{ts}_{custom_filename}.png"
    winner_path = os.path.join(output_dir, winner_filename)
    shutil.copy2(best_path, winner_path)

    winner_normalized = os.path.abspath(winner_path).replace("\\", "/")
    _log(f"SELECTED -> {os.path.basename(winner_path)}")
    return True, [winner_normalized]


# -- find latest panel output (for img2img chaining) -----------------------

def _find_latest_panel_output(output_dir: str, title_tag: str, panel_id: str) -> Optional[str]:
    """Find the newest output image for a panel."""
    tag_lower = title_tag.lower()
    pid_lower = panel_id.lower()
    best = None
    best_mtime = 0
    try:
        for fname in os.listdir(output_dir):
            fl = fname.lower()
            if not fl.endswith(".png"):
                continue
            if fl.endswith(("_bg.png", "_char.png", "_mask.png")):
                continue
            if tag_lower in fl and pid_lower in fl:
                fpath = os.path.join(output_dir, fname)
                mtime = os.path.getmtime(fpath)
                if mtime > best_mtime:
                    best = fpath
                    best_mtime = mtime
    except FileNotFoundError:
        pass
    return best


# -- single panel generation ------------------------------------------------

def generate_panel(
    script: Dict[str, Any],
    panel: Dict[str, Any],
    page: Dict[str, Any],
    output_dir: str,
    title_tag: str,
    timestamp: str,
    page_seed: int = -1,
    composite: bool = False,
    num_candidates: int = 1,
    scorer: Optional[PanelScorer] = None,
    generated_paths: Optional[Dict[str, str]] = None,
    adetailer_settings: Optional[Dict] = None,
    log: Optional[Callable] = None,
) -> bool:
    """
    Generate images for one panel.  Returns True on success.

    Dispatches to the appropriate mode:
      - Composite: bg + character + rembg merge
      - Candidates: multi-seed with scoring
      - img2img chain: uses a previous panel as init_image
      - Standard: single txt2img call
    """
    def _log(msg):
        if log:
            log(msg)

    gen = script.get("generation", {})
    character = resolve_panel_character(script, panel)
    title = script.get("title", "Untitled")

    base_positive = gen.get("base_positive", "")
    base_negative = gen.get("base_negative", "")

    shot_type = panel.get("shot") or infer_shot_type(
        panel.get("scene", ""), panel.get("positive_extra", ""),
        panel.get("no_character", False),
    )
    shot_token = get_shot_token(shot_type, 0) if num_candidates <= 1 else ""

    prompt = build_panel_prompt(character, panel, base_positive, shot_token=shot_token)
    negative = _build_negative(base_negative, panel.get("negative_extra", ""), character)
    if character is None:
        no_person = "1girl, solo, person, human, figure"
        negative = f"{no_person}, {negative}" if negative else no_person

    # Log resolved character and prompt so multi-char issues are visible
    if character is not None:
        _log(f"  char: {character.get('lora', '?')} (w={character.get('weight', '?')})")
    else:
        _log(f"  char: none (background/no-character panel)")
    _log(f"  prompt: {prompt[:140]}{'...' if len(prompt) > 140 else ''}")

    width = panel.get("width") or gen.get("width", 1024)
    height = panel.get("height") or gen.get("height", 1280)

    do_hires = panel.get("hires", False)
    if not do_hires and panel_needs_auto_hires(panel, page):
        do_hires = True
    hr_denoise = panel.get("hr_denoise", 0.5)

    steps = gen.get("steps", 27)
    cfg = gen.get("cfg", 6.0)
    sampler = gen.get("sampler", "Euler a")
    batch = gen.get("batch", 1)
    # adetailer_settings not None = explicitly enabled from UI; None = use script flag
    if character is None:
        do_adetailer = False
    elif adetailer_settings is not None:
        do_adetailer = True
    else:
        do_adetailer = gen.get("adetailer", True)

    # -- Seed hierarchy: explicit panel > scene-based > page-based > random --
    seed = panel.get("seed", -1)
    if seed == -1:
        scene_tag = panel.get("scene_tag")
        if scene_tag:
            seed = compute_scene_seed(title, scene_tag)
        elif page_seed != -1:
            seed = page_seed

    panel_id = panel.get("id", "unknown")
    custom_filename = f"{title_tag}_{panel_id}"

    # -- Resolve img2img chain source --
    init_from = panel.get("init_from")
    init_image_path = None
    if init_from and generated_paths and init_from in generated_paths:
        init_image_path = generated_paths[init_from]

    # -- Composite mode --
    use_composite = panel.get("composite", False) or composite
    if use_composite and character is not None:
        ok, path = generate_panel_composite(
            script=script, panel=panel, page=page,
            character=character, prompt=prompt, negative=negative,
            width=width, height=height, steps=steps, cfg=cfg,
            sampler=sampler, seed=seed, do_hires=do_hires,
            hr_denoise=hr_denoise, output_dir=output_dir,
            custom_filename=f"{timestamp}_{custom_filename}",
            adetailer_settings=adetailer_settings, log=log,
        )
        if ok and generated_paths is not None and path:
            generated_paths[panel_id] = path
        return ok

    # -- Multi-candidate mode --
    effective_candidates = max(num_candidates, batch)
    if effective_candidates > 1:
        ok, files = generate_panel_candidates(
            script=script, panel=panel, page=page,
            output_dir=output_dir, title_tag=title_tag,
            timestamp=timestamp, base_seed=seed,
            num_candidates=effective_candidates, scorer=scorer,
            init_image_path=init_image_path,
            adetailer_settings=adetailer_settings, log=log,
        )
        if ok and files and generated_paths is not None:
            generated_paths[panel_id] = files[0]
        return ok

    # -- img2img chain mode --
    if init_image_path and os.path.isfile(init_image_path):
        init_denoise = panel.get("init_denoise", 0.45)
        ok, files = generate_panel_img2img(
            prompt, negative, width, height,
            steps, cfg, sampler, seed, do_adetailer,
            init_image_path, init_denoise,
            output_dir, f"{timestamp}_{custom_filename}",
            adetailer_settings=adetailer_settings, log=log,
        )
        if ok and files and generated_paths is not None:
            generated_paths[panel_id] = files[0]
        return ok

    # -- Standard single txt2img --
    gen_engine._set_job(f"Panel {panel_id}")

    ok, msg, files, _imgs = gen_engine.generate_txt2img(
        prompt=prompt,
        negative_prompt=negative,
        steps=steps,
        sampler_name=sampler,
        cfg_scale=cfg,
        width=width,
        height=height,
        enable_hr=do_hires,
        hr_scale=1.5,
        hr_upscaler="Latent",
        denoising_strength=hr_denoise,
        enable_adetailer=do_adetailer,
        adetailer_settings=adetailer_settings,
        seed=seed,
        batch_size=1,
        output_dir=output_dir,
        custom_filename=f"{timestamp}_{custom_filename}",
    )

    status = "OK" if ok else "FAIL"
    _log(f"{status} - {msg}")

    if ok and files and generated_paths is not None:
        generated_paths[panel_id] = files[0]

    return ok


# -- preview / list mode ----------------------------------------------------

def preview_script(script: Dict[str, Any], source_label: str = "") -> str:
    """Return a markdown summary of every panel without generating anything."""
    title = script.get("title", "Untitled")
    gen = script.get("generation", {})
    panels = list(iter_panels(script))
    lines = []

    lines.append(f"### {title} ({len(panels)} panels)")
    if source_label:
        lines.append(f"Source: {source_label}")

    characters = script.get("characters")
    if characters:
        for cname, cdata in characters.items():
            lines.append(f"- Character **{cname}**: {cdata.get('lora', '?')} (w={cdata.get('weight', '?')})")
    else:
        character = script.get("character", {})
        lines.append(f"- Character: {character.get('lora', '?')} (w={character.get('weight', '?')})")

    lines.append(f"- Defaults: {gen.get('width', '?')}x{gen.get('height', '?')}, "
                 f"steps={gen.get('steps', '?')}, cfg={gen.get('cfg', '?')}, "
                 f"sampler={gen.get('sampler', '?')}")
    lines.append("")

    for pi, qi, panel, page in panels:
        pid = panel.get("id", "?")
        scene = panel.get("scene", "")
        scene_preview = scene[:90] + ("..." if len(scene) > 90 else "")

        flags = []
        if panel.get("width") or panel.get("height"):
            flags.append(f"{panel.get('width', '?')}x{panel.get('height', '?')}")
        if panel.get("hires"):
            flags.append(f"hires(d={panel.get('hr_denoise', 0.5)})")
        if panel.get("seed", -1) != -1:
            flags.append(f"seed={panel['seed']}")
        if panel.get("reuse"):
            flags.append(f"reuse={panel['reuse']}")
        if panel.get("composite"):
            flags.append("composite")
        if panel.get("no_character"):
            flags.append("no_char")
        if panel.get("init_from"):
            flags.append(f"img2img={panel['init_from']}")
        if panel.get("scene_tag"):
            flags.append(f"scene={panel['scene_tag']}")
        # Show resolved character for multi-char scripts
        resolved_char = resolve_panel_character(script, panel)
        if script.get("characters"):
            char_key = panel.get("character")
            if resolved_char is not None:
                flags.append(f"char={char_key}({resolved_char.get('lora', '?')})")
            elif not panel.get("no_character"):
                flags.append(f"char=UNRESOLVED(key={char_key!r})")

        shot = panel.get("shot") or infer_shot_type(
            scene, panel.get("positive_extra", ""),
            panel.get("no_character", False),
        )
        flags.append(f"shot={shot}")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"**Page {pi+1} Panel {qi+1}** `{pid}`{flag_str}")
        if scene_preview:
            lines.append(f"  scene: {scene_preview}")
        if panel.get("caption"):
            caption = panel["caption"][:70] + ("..." if len(panel["caption"]) > 70 else "")
            lines.append(f"  caption: _{caption}_")
        if panel.get("dialogue"):
            dialogue = panel["dialogue"][:70] + ("..." if len(panel["dialogue"]) > 70 else "")
            lines.append(f"  dialogue: \"{dialogue}\"")

    # Camera continuity check
    cam_warnings = validate_camera_continuity(script)
    if cam_warnings:
        warn_lines = ["**⚠ Camera continuity warnings**"] + cam_warnings
        warn_block = (
            '<div style="background:#2a1f00;border-left:4px solid #ff9800;'
            'padding:8px 14px;border-radius:4px;margin-top:12px;">'
            + "<br>".join(warn_lines)
            + "</div>"
        )
        lines.append("")
        lines.append(warn_block)

    return "\n".join(lines)


# -- main runner ------------------------------------------------------------

def run_comic_script(
    script: Dict[str, Any],
    output_dir: str,
    cooldown: float = 2.0,
    only_panels: Optional[Set[str]] = None,
    skip_existing: bool = False,
    composite: bool = False,
    num_candidates: int = 1,
    adetailer_settings: Optional[Dict] = None,
    log: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Generate images for all panels in a comic script.

    Args:
        script: Parsed comic script dict.
        output_dir: Where to save generated images.
        cooldown: Seconds between generations.
        only_panels: If set, only generate these panel IDs.
        skip_existing: Skip panels that already have output images.
        composite: Force composite mode for all panels.
        num_candidates: Number of candidates per panel.
        log: Callback function for progress messages.

    Returns:
        Dict with 'generated', 'skipped', 'total', 'output_dir' keys.
    """
    def _log(msg):
        if log:
            log(msg)

    title = script.get("title", "Untitled")
    title_tag = make_title_tag(title)
    panels = list(iter_panels(script))
    total = len(panels)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    os.makedirs(output_dir, exist_ok=True)

    # Scorer for multi-candidate mode
    gen = script.get("generation", {})
    batch = gen.get("batch", 1)
    effective_candidates = max(num_candidates, batch)
    scorer = None
    if effective_candidates > 1:
        scorer = PanelScorer()
        _log(f"Candidates: {effective_candidates} per panel (auto-score)")

    # Track generated outputs for img2img chaining
    generated_paths: Dict[str, str] = {}

    _log(f"=== Comic: {title} ({total} panels) ===")
    _log(f"Output: {os.path.abspath(output_dir)}")

    generated = 0
    skipped = 0

    for idx, (pi, qi, panel, page) in enumerate(panels):
        # Check for interrupt
        if gen_engine._check_interrupted():
            _log("Generation interrupted by user")
            break

        panel_id = panel.get("id", f"page{pi+1}_panel{qi+1}")
        scene = panel.get("scene", "")
        scene_preview = scene[:80] + ("..." if len(scene) > 80 else "")

        _log(f"[{idx+1}/{total}] {panel_id}")
        if scene_preview:
            _log(f"  scene: {scene_preview}")

        gen_engine._set_job(f"Comic: {panel_id} ({idx+1}/{total})")

        # skip: reuse flag
        if panel.get("reuse"):
            _log(f"  SKIP - reuse={panel['reuse']}")
            skipped += 1
            continue

        # skip: panel not in only list
        if only_panels and panel_id not in only_panels:
            _log(f"  SKIP - not in filter list")
            skipped += 1
            found = _find_latest_panel_output(output_dir, title_tag, panel_id)
            if found:
                generated_paths[panel_id] = found
            continue

        # skip: output already exists
        if skip_existing and panel_already_generated(output_dir, title_tag, panel_id):
            _log(f"  SKIP - images already exist")
            skipped += 1
            found = _find_latest_panel_output(output_dir, title_tag, panel_id)
            if found:
                generated_paths[panel_id] = found
            continue

        page_seed = compute_page_seed(title, pi)
        ok = generate_panel(
            script, panel, page, output_dir, title_tag, timestamp,
            page_seed=page_seed, composite=composite,
            num_candidates=num_candidates, scorer=scorer,
            generated_paths=generated_paths,
            adetailer_settings=adetailer_settings, log=log,
        )
        if ok:
            generated += 1

        if idx < total - 1:
            time.sleep(cooldown)

    _log(f"=== Finished: {title} ===")
    _log(f"Generated: {generated}  Skipped: {skipped}  Total: {total}")

    return {
        "generated": generated,
        "skipped": skipped,
        "total": total,
        "output_dir": output_dir,
    }
