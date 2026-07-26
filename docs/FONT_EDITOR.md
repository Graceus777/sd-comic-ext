# Font Editor guide

The Comic Generator's **Font Editor** is a visual lettering workspace for dialogue, narration, thought bubbles, exclamations, and sound effects. It edits the active JSON from the **Comic** tab, so lettering remains reproducible whenever pages are reassembled.

## Quick start

1. Open or create a script on the **Comic** tab.
2. Open **Font Editor** and click **Refresh Panels**.
3. Select a panel. The layer list refreshes automatically.
4. Select **Dialogue bubble**, **Caption / narration**, or an existing extra layer, then click **Load Layer**.
5. Change the text, preset, font, position, size, rotation, or colors.
6. Click **Preview** to test the current controls without changing the script.
7. Click **Apply to Script** to save the selected layer into the JSON editor.
8. Reassemble the comic to render the saved lettering into the final pages.

Use **Add as New Layer** when a panel needs another bubble or a sound effect. Use **Remove Layer** to clear the selected built-in layer or delete an extra layer.

## Preview image sources

The editor looks for the selected panel's generated image under `comics/{title}/pages` by default. Expand **Preview image source** to choose another generated-panel directory or upload a panel image directly. An uploaded image takes priority.

If no image is available, the editor uses a placement grid. The text layout is still representative of final assembly.

## Controls

| Control | Meaning |
| --- | --- |
| Preset | Bubble, caption, or boxless effect appearance |
| Font family | Portable logical font name or extension-local custom font |
| 9-grid position | Initial top/center/bottom and left/center/right placement |
| Horizontal nudge | Additional X offset as a percentage of panel width |
| Vertical nudge | Additional Y offset as a percentage of panel height |
| Layer width | Text wrapping or bubble width as a percentage of panel width |
| Font size | Base size at a 1200px-wide panel; assembly scales it proportionally |
| Rotation | Clockwise rotation from -45 to 45 degrees |
| Text color | `#RRGGBB` glyph color |
| Text outline color | `#RRGGBB` stroke color for presets that use a glyph outline |

Positive X moves right. Positive Y moves down. The renderer constrains layers to the panel, though rotated text near an edge can still be clipped.

## Presets

### Bubbles

| Key | Appearance | Typical use |
| --- | --- | --- |
| `speech` | Rounded white bubble with tail | Normal dialogue |
| `thought` | Cloud bubble with dotted tail | Internal monologue |
| `shout` | Jagged exclamation burst | Shouting or alarm |
| `whisper` | Translucent dashed bubble | Quiet speech |
| `radio` | Blue rectangular off-panel bubble | Radio, phone, or machine voice |

### Captions

| Key | Appearance |
| --- | --- |
| `narration` | Dark full-width narration bar |
| `caption_box` | White caption box |
| `yellow_box` | Yellow comic caption box |
| `parchment` | Rounded parchment-colored box |

### Boxless sound effects

| Key | Appearance | Examples |
| --- | --- | --- |
| `sfx` | Yellow impact lettering | `POW!`, `KRAK!` |
| `sfx_speed` | Pale blue speed lettering | `WHOOSH`, `FWIP` |
| `sfx_horror` | Dark red menace lettering | `SKRITCH`, `DRIP` |
| `sfx_electric` | White and electric-blue lettering | `ZZZT`, `KRA-KOOM!` |
| `sfx_subtle` | Small handwritten ambient lettering | `tap`, `rustle` |

## Font families and custom fonts

Built-in logical families are `comic`, `handwritten`, `impact`, `sans`, `serif`, and `mono`. The renderer resolves each family to an installed Windows or Linux font and falls back safely when the preferred font is unavailable.

For custom fonts:

1. Copy a `.ttf`, `.otf`, or `.ttc` file into `sd-comic-ext/fonts/`.
2. Restart the WebUI or reload the extension.
3. Select `Custom: filename` in the Font Editor.

The JSON stores the logical value `custom:filename`, not an absolute path. Keep the same font file in `fonts/` when moving the extension to another machine. Ensure the font's license permits your intended distribution.

## Script schema

Dialogue and captions remain compatible with existing scripts:

```json
{
  "dialogue": "We need to move!",
  "dialogue_style": "speech",
  "dialogue_font": "comic",
  "dialogue_anchor": "bottom-left",
  "dialogue_offset": [2, -4],
  "dialogue_width": 55,
  "dialogue_font_size": 30,
  "dialogue_rotation": 0,
  "dialogue_color": "#0f0f0f",
  "dialogue_outline_color": "#000000"
}
```

Replace `dialogue_` with `caption_` for the caption layer.

Additional layers live in the panel's `lettering` array and render after caption and dialogue:

```json
{
  "id": "p0101",
  "scene": "lightning strikes behind the hero",
  "lettering": [
    {
      "id": "fx1",
      "text": "KRA-KOOM!",
      "style": "sfx_electric",
      "font": "impact",
      "anchor": "center-right",
      "offset": [-4, 3],
      "width": 58,
      "font_size": 68,
      "rotation": 8,
      "color": "#ffffff",
      "outline_color": "#2355e6"
    }
  ]
}
```

Extra layer IDs are assigned automatically as `fx1`, `fx2`, and so on.

## Rendering order and compatibility

Assembly renders caption first, dialogue second, and extra `lettering` layers in array order. Older scripts containing only `caption` and `dialogue` continue to work. Unknown style names, invalid positions, missing fonts, malformed numeric values, and invalid colors fall back to safe defaults instead of stopping assembly.

## Troubleshooting

### The panel list is empty

Return to **Comic**, load or create valid JSON containing a `pages` array, then click **Refresh Panels** again.

### The preview uses a grid

The generated image was not found. Set **Generated panel directory** to the folder containing panel PNGs or upload the panel image.

### A custom font does not appear

Confirm the file is directly inside `fonts/`, uses a supported extension, and the WebUI was restarted or the extension reloaded.

### Lettering overlaps another layer

Load each layer individually and adjust its 9-grid position, X/Y nudge, or width. Extra layers render in their JSON array order.

### Lettering is clipped

Reduce rotation, width, or font size, or move the layer away from the panel edge.
