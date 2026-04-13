"""
Short-form comic strip engine.

Ported from generate_strip.py — combines scenario templates with characters
and NSFW scene LoRAs, then delegates to comic_engine for generation and
assembler for page assembly.

Scenario sources:
  - File-based: storyboards/strips/*.json
  - Procedural: scenario_generator.generate_scenario()
"""
import os
import json
import random
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .shared import EXT_DIR, STRIPS_DIR, LORA_TEXTS_DIR
from . import comic_engine
from . import assembler
from .prompt_builder import SHOT_DICTION, get_shot_token


# -- paths ------------------------------------------------------------------

NSFW_DIR = LORA_TEXTS_DIR / "nsfw_scenes"


# -- NSFW scene LoRA loader -------------------------------------------------

def load_scene_loras() -> Tuple[List[Dict], List[Dict]]:
    """Load NSFW scene LoRAs from folders 1 and 2.

    Returns (phase1_loras, phase2_loras).
    Each entry: {"name", "lora", "activation", "weight", "negative"}
    """
    def _load_folder(folder: str) -> List[Dict]:
        items = []
        path = NSFW_DIR / folder
        if not path.is_dir():
            return items
        for fname in sorted(os.listdir(path)):
            if not fname.endswith(".json"):
                continue
            with open(path / fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            stem = os.path.splitext(fname)[0]
            items.append({
                "name": stem,
                "lora": stem,
                "activation": data.get("activation text", ""),
                "weight": data.get("preferred weight", 0.8),
                "negative": data.get("negative text", ""),
            })
        return items

    return _load_folder("1"), _load_folder("2")


# -- character pool ---------------------------------------------------------

def load_characters_json() -> Dict[str, Dict]:
    """Load character definitions from characters.json in extension root."""
    chars_file = EXT_DIR / "characters.json"
    if not chars_file.is_file():
        # Fall back to repo root
        chars_file = EXT_DIR.parent / "characters.json"
    if not chars_file.is_file():
        return {}
    with open(chars_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("characters", {})


def load_lora_characters() -> Dict[str, Dict]:
    """Load characters from A1111's LoRA directory (and lora_texts/ fallback)."""
    try:
        from .shared import find_lora_dirs
        from .scenario_generator import load_lora_characters as _load
        return _load(find_lora_dirs())
    except Exception:
        return load_characters_json()


def pick_character(chars: Dict, key: Optional[str] = None) -> Tuple[str, Dict]:
    """Pick a character by key or randomly."""
    if key:
        if key not in chars:
            raise ValueError(f"Character '{key}' not found. Available: {list(chars.keys())}")
        return key, chars[key]
    key = random.choice(list(chars.keys()))
    return key, chars[key]


# -- scenario loader --------------------------------------------------------

def list_file_scenarios() -> List[str]:
    """List available file-based scenario names."""
    strips_dir = str(STRIPS_DIR)
    if not os.path.isdir(strips_dir):
        return []
    return [
        os.path.splitext(f)[0]
        for f in sorted(os.listdir(strips_dir))
        if f.endswith(".json")
    ]


def load_file_scenario(name: str) -> Dict:
    """Load a scenario template JSON from storyboards/strips/."""
    path = STRIPS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_procedural_settings() -> List[str]:
    """List available procedural scenario setting keys."""
    try:
        from .scenario_generator import list_settings
        return list_settings()
    except Exception:
        return []


def generate_procedural_scenario(setting_key: Optional[str] = None) -> Dict:
    """Generate a procedural scenario from scenario_generator."""
    from .scenario_generator import generate_scenario, get_setting, SETTINGS
    if setting_key:
        setting = get_setting(setting_key)
    else:
        setting = random.choice(SETTINGS)
    return generate_scenario(setting), setting["key"]


# -- script builder ---------------------------------------------------------

def build_strip_script(
    scenario: Dict,
    char_key: str,
    char_data: Dict,
    phase1: List[Dict],
    phase2: List[Dict],
) -> Dict:
    """Build a complete comic script from a scenario template.

    Panels with "scene_lora": "phase1"/"phase2"/"phase1_or_2" get a random
    LoRA from the corresponding pool injected into their prompt.
    """
    title = scenario["title"]
    char_tag = char_key.replace("_", " ").title()

    p1 = list(phase1)
    p2 = list(phase2)
    random.shuffle(p1)
    random.shuffle(p2)
    p1_idx = 0
    p2_idx = 0

    script = {
        "title": f"{title} — {char_tag}",
        "character": {
            "lora": char_data["lora"],
            "activation": char_data["activation"],
            "weight": char_data.get("weight", 0.8),
        },
        "generation": scenario.get("generation", {
            "steps": 30,
            "cfg": 7.0,
            "width": 1024,
            "height": 1280,
            "batch": 1,
            "sampler": "Euler a",
            "adetailer": True,
            "base_positive": "lazypos",
            "base_negative": "lazyneg",
        }),
        "pages": [],
    }

    for page in scenario["pages"]:
        new_page = {
            "_comment": page.get("_comment", ""),
            "layout": page.get("layout", "three_row"),
            "panels": [],
        }

        for panel in page["panels"]:
            new_panel = dict(panel)

            phase = panel.get("scene_lora")
            scene_lora = None
            if phase == "phase1" and p1:
                scene_lora = p1[p1_idx % len(p1)]
                p1_idx += 1
            elif phase == "phase2" and p2:
                scene_lora = p2[p2_idx % len(p2)]
                p2_idx += 1
            elif phase == "phase1_or_2":
                pool = p1 + p2
                if pool:
                    scene_lora = random.choice(pool)

            if scene_lora:
                lora_tag = f"<lora:{scene_lora['lora']}:{scene_lora['weight']}>"
                activation = scene_lora["activation"]
                existing_extra = new_panel.get("positive_extra", "")
                new_panel["positive_extra"] = f"{lora_tag}, {activation}, {existing_extra}".strip(", ")
                if scene_lora.get("negative"):
                    existing_neg = new_panel.get("negative_extra", "")
                    new_panel["negative_extra"] = f"{scene_lora['negative']}, {existing_neg}".strip(", ")
                new_panel.pop("scene_lora", None)

            new_page["panels"].append(new_panel)

        script["pages"].append(new_page)

    return script


# -- preview ----------------------------------------------------------------

def preview_strip(script: Dict) -> str:
    """Return a markdown preview of the strip script."""
    return comic_engine.preview_script(script, source_label="Strip engine")


# -- generation + assembly --------------------------------------------------

def run_strip(
    scenario_name: str,
    scenario: Dict,
    char_key: str,
    char_data: Dict,
    phase1: List[Dict],
    phase2: List[Dict],
    output_base: str = "comics/strips",
    skip_existing: bool = True,
    num_candidates: int = 1,
    cooldown: float = 2.0,
    log: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Build, generate, and assemble a single strip.

    Returns dict with 'script', 'script_path', 'output_dir', 'pages', 'gen_result'.
    """
    def _log(msg):
        if log:
            log(msg)

    script = build_strip_script(scenario, char_key, char_data, phase1, phase2)

    strip_dir = os.path.join(output_base, f"{scenario_name}_{char_key}")
    os.makedirs(strip_dir, exist_ok=True)

    # Save script for reference
    script_path = os.path.join(strip_dir, "script.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    _log(f"Script saved: {script_path}")

    # Generate panels
    panels_dir = os.path.join(strip_dir, "pages")
    gen_result = comic_engine.run_comic_script(
        script=script,
        output_dir=panels_dir,
        cooldown=cooldown,
        skip_existing=skip_existing,
        num_candidates=num_candidates,
        log=log,
    )

    # Assemble pages
    _log("Assembling pages...")
    assembled_dir = os.path.join(strip_dir, "assembled")
    pages = assembler.assemble_from_script_data(
        script=script,
        image_dirs=[panels_dir],
        output_dir=assembled_dir,
    )

    _log(f"Output: {os.path.abspath(strip_dir)}")

    return {
        "script": script,
        "script_path": script_path,
        "output_dir": strip_dir,
        "panels_dir": panels_dir,
        "assembled_dir": assembled_dir,
        "pages": pages,
        "gen_result": gen_result,
    }


def run_batch_strips(
    count: int,
    char_keys: Optional[List[str]] = None,
    setting_key: Optional[str] = None,
    output_base: str = "comics/strips",
    skip_existing: bool = True,
    num_candidates: int = 1,
    cooldown: float = 2.0,
    log: Optional[Callable] = None,
) -> List[Dict]:
    """Generate multiple strips with procedural scenarios.

    Returns list of run_strip result dicts.
    """
    from . import generation_engine as gen_engine

    def _log(msg):
        if log:
            log(msg)

    chars = load_lora_characters()
    if not chars:
        _log("No characters found in lora_texts/")
        return []

    phase1, phase2 = load_scene_loras()
    _log(f"Scene LoRAs: {len(phase1)} phase1, {len(phase2)} phase2")
    _log(f"Characters: {len(chars)}")

    results = []
    for i in range(count):
        if gen_engine._check_interrupted():
            _log("Batch interrupted by user")
            break

        # Pick character
        if char_keys:
            ck = char_keys[i % len(char_keys)]
            if ck in chars:
                cd = chars[ck]
            else:
                ck, cd = pick_character(chars)
        else:
            ck, cd = pick_character(chars)

        # Generate scenario
        if setting_key:
            scenario, sname = generate_procedural_scenario(setting_key)
        else:
            scenario, sname = generate_procedural_scenario()

        _log(f"\n[Strip {i+1}/{count}] Setting: {sname} | Char: {ck}")

        result = run_strip(
            scenario_name=sname,
            scenario=scenario,
            char_key=ck,
            char_data=cd,
            phase1=phase1,
            phase2=phase2,
            output_base=output_base,
            skip_existing=skip_existing,
            num_candidates=num_candidates,
            cooldown=cooldown,
            log=log,
        )
        results.append(result)

    return results
