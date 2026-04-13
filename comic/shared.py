"""
Shared paths, constants, and configuration for the Comic Generator extension.
"""
import os
import json
from pathlib import Path
from typing import List

# Extension root: sd-comic-ext/
EXT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data directories
LORA_TEXTS_DIR = EXT_DIR / "lora_texts"
CONFIGS_DIR = EXT_DIR / "configs"
STORYBOARDS_DIR = EXT_DIR / "storyboards"
STRIPS_DIR = STORYBOARDS_DIR / "strips"

# Files
CONFIG_FILE = EXT_DIR / "config.json"
HISTORY_FILE = EXT_DIR / "generation_history.jsonl"

# Default configuration
DEFAULT_CONFIG = {
    "defaults": {
        "positive_prompt": "masterpiece, best quality, sharp focus, highres",
        "negative_prompt": "(low quality, worst quality:1.4)",
        "steps": 27,
        "sampler": "Euler a",
        "cfg_scale": 6.0,
        "width": 1024,
        "height": 1280,
        "batch_size": 1,
        "cooldown": 0,
    },
}


def load_config() -> dict:
    """Load extension configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save extension configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# Module-level config singleton
config = load_config()


def find_lora_dirs() -> List[Path]:
    """Find all directories that may contain character LoRA JSON cards.

    Search order:
      1. A1111's configured lora_dir (from shared.opts, if available)
      2. Derived from extension location: {webui_root}/models/Lora/
         + any immediate subdirectories (Characters/, etc.)
      3. Extension's own lora_texts/ as a fallback for manual entries

    Returns a de-duplicated list of existing directories.
    """
    seen: set = set()
    dirs: List[Path] = []

    def _add(p: Path):
        p = p.resolve()
        if p not in seen and p.is_dir():
            seen.add(p)
            dirs.append(p)

    lora_root: Path | None = None

    # 1. Try A1111's runtime opts
    try:
        from modules import shared as a1111_shared
        opt_dir = getattr(a1111_shared.opts, "lora_dir", None)
        if opt_dir:
            candidate = Path(opt_dir)
            if candidate.is_dir():
                lora_root = candidate
    except Exception:
        pass

    # 2. Derive from extension location
    #    Extension lives at {webui}/extensions/{ext_name}/
    #    so webui root is EXT_DIR.parent.parent
    if lora_root is None:
        candidate = EXT_DIR.parent.parent / "models" / "Lora"
        if candidate.is_dir():
            lora_root = candidate

    if lora_root is not None:
        _add(lora_root)
        # Add immediate subdirectories (Characters/, styles/, etc.)
        try:
            for sub in sorted(lora_root.iterdir()):
                if sub.is_dir():
                    _add(sub)
        except PermissionError:
            pass

    # 3. Always include extension's own lora_texts/ as fallback
    _add(LORA_TEXTS_DIR)

    return dirs
