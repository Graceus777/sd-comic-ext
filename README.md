# sd-comic-ext

A1111 WebUI extension for generating multi-page comics from structured JSON scripts.

## Features

- **Script-driven generation** — define characters, layouts, scenes, and camera angles in JSON
- **12 page layouts** — splash, grid, L-shape, staircase, strip, and more
- **Multi-candidate scoring** — generate N candidates per panel, auto-select the best (sharpness, aesthetics, CLIP content match)
- **Scene-based seeding** — panels sharing a scene tag get consistent lighting/color via deterministic seeds
- **img2img chaining** — reference earlier panels as init images for pose-to-pose continuity
- **Composite mode** — separate background/character generation with rembg masking
- **Camera vocabulary** — 11 shot types with diction variants, auto-inferred from scene text
- **Page assembly** — PIL-based compositing with captions and dialogue bubbles
- **Export** — PDF and CBZ output
- **Script Wizard** — pick characters and a format, get a JSON template + LLM prompt to fill it
- **Scenario generator** — procedural strip templates for quick one-click generation

## Requirements

- [A1111 WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) with `--api` flag
- Python 3.10+
- Character LoRAs with activation text
- ADetailer extension (optional, recommended)

## Installation

Clone into your A1111 extensions folder:

```
cd stable-diffusion-webui/extensions
git clone https://github.com/Graceus777/sd-comic-ext.git
```

Dependencies (`rembg`, `Pillow`) are installed automatically on first launch via `install.py`.

Restart the WebUI. A **Comic Generator** tab will appear.

## Usage

1. Open the **Comic Generator** tab in WebUI
2. Use the **Script Wizard** to generate a JSON template, or write one manually
3. Edit scene prompts, layouts, and camera angles in the script editor
4. Click **Generate** to produce panels and assemble pages
5. Export to PDF/CBZ from the Assembly sub-tab

## Script format

```json
{
  "title": "My Comic",
  "characters": {
    "character_name": {
      "lora": "LoraFilename",
      "activation": "trigger words here",
      "weight": 0.85
    }
  },
  "generation": {
    "steps": 30,
    "cfg": 7.0,
    "width": 1024,
    "height": 1280,
    "sampler": "Euler a"
  },
  "pages": [
    {
      "layout": "l_right",
      "panels": [
        {
          "id": "p001",
          "character": "character_name",
          "scene": "description of the panel",
          "shot": "medium"
        }
      ]
    }
  ]
}
```

## License

MIT
