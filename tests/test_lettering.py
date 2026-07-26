import json
import unittest

from PIL import Image, ImageChops, ImageDraw

from comic import assembler, lettering, text_styles


class LetteringScriptTests(unittest.TestCase):
    def setUp(self):
        self.script = {
            "title": "Lettering test",
            "pages": [{
                "layout": "splash",
                "panels": [{
                    "id": "p0101",
                    "scene": "A test panel",
                    "dialogue": "Hello",
                }],
            }],
        }
        self.raw = json.dumps(self.script)

    def test_add_load_edit_and_remove_extra_layer(self):
        values = {
            "text": "KRAK!",
            "style": "sfx_electric",
            "font": "impact",
            "anchor": "center-right",
            "x": -5,
            "y": 3,
            "width": 60,
            "font_size": 70,
            "rotation": 8,
            "color": "#ffffff",
            "outline_color": "#2255ee",
        }
        updated, layer_ref = lettering.update_json(
            self.raw, "0:0", "dialogue", values, add_new=True
        )
        self.assertEqual(layer_ref, "extra:0")
        script = lettering.parse_script(updated)
        _, panel, _, _ = lettering.get_panel(script, "0:0")
        loaded = lettering.layer_values(panel, layer_ref)
        self.assertEqual(loaded["text"], "KRAK!")
        self.assertEqual(loaded["font"], "impact")
        self.assertEqual(loaded["rotation"], 8)
        self.assertEqual(len(lettering.layer_choices(panel)), 3)

        blank = dict(values, text="")
        removed, selected = lettering.update_json(
            updated, "0:0", layer_ref, blank
        )
        self.assertEqual(selected, "dialogue")
        panel = lettering.parse_script(removed)["pages"][0]["panels"][0]
        self.assertNotIn("lettering", panel)

    def test_core_layer_values_are_clamped_and_clearable(self):
        values = {
            "text": "Think small.",
            "style": "thought",
            "font": "handwritten",
            "anchor": "top",
            "x": 999,
            "y": -999,
            "width": 3,
            "font_size": 999,
            "rotation": 90,
            "color": "bad",
            "outline_color": "#abc",
        }
        updated, _ = lettering.update_json(
            self.raw, "0:0", "dialogue", values
        )
        panel = lettering.parse_script(updated)["pages"][0]["panels"][0]
        self.assertEqual(panel["dialogue_anchor"], "top-center")
        self.assertEqual(panel["dialogue_offset"], [50, -50])
        self.assertEqual(panel["dialogue_width"], 15)
        self.assertEqual(panel["dialogue_font_size"], 140)
        self.assertEqual(panel["dialogue_rotation"], 45)
        self.assertEqual(panel["dialogue_outline_color"], "#aabbcc")
        self.assertEqual(panel["dialogue_color"], "#23232d")

        cleared = lettering.remove_from_json(updated, "0:0", "dialogue")
        panel = lettering.parse_script(cleared)["pages"][0]["panels"][0]
        self.assertNotIn("dialogue", panel)
        self.assertFalse(any(key.startswith("dialogue_") for key in panel))


class LetteringRendererTests(unittest.TestCase):
    def test_every_preset_renders(self):
        for style_name in text_styles.STYLES:
            with self.subTest(style=style_name):
                image = Image.new("RGBA", (600, 700), (50, 50, 55, 255))
                assembler.draw_text_element(
                    image,
                    "SUPERCALIFRAGILISTICEXPLOSION",
                    text_styles.get_style(style_name),
                    anchor="center",
                    width_frac=0.35,
                    font_px=42,
                    font_family="impact",
                    rotation=7,
                )
                self.assertEqual(image.mode, "RGBA")

    def test_legacy_wrappers_accept_rgb_images(self):
        image = Image.new("RGB", (500, 600), "navy")
        assembler.draw_caption_overlay(image, "Narration")
        assembler.draw_dialogue_overlay(image, "Dialogue")
        self.assertEqual(image.mode, "RGB")

    def test_wrap_text_honors_newlines_and_long_words(self):
        image = Image.new("RGB", (400, 200))
        draw = ImageDraw.Draw(image)
        font = assembler.get_font(24, family="sans")
        lines = assembler.wrap_text(
            "first line\nSUPERCALIFRAGILISTICEXPLOSION", font, 100, draw
        )
        self.assertEqual(lines[0], "first line")
        self.assertTrue(all(
            draw.textbbox((0, 0), line, font=font)[2] <= 100
            for line in lines if line
        ))

    def test_multiple_panel_layers_render_together(self):
        panel = {
            "caption": "Meanwhile...",
            "caption_style": "yellow_box",
            "dialogue": "Look out!",
            "dialogue_style": "shout",
            "lettering": [
                {
                    "id": "fx1", "text": "ZZZT", "style": "sfx_electric",
                    "font": "impact", "anchor": "center-right",
                    "offset": [0, 0], "width": 45, "font_size": 50,
                    "rotation": 9, "color": "#ffffff",
                    "outline_color": "#2255ee",
                }
            ],
        }
        image = Image.new("RGBA", (800, 1000), (60, 65, 75, 255))
        before = image.copy()
        assembler.render_panel_lettering(image, panel)
        self.assertIsNotNone(ImageChops.difference(image.convert("RGB"), before.convert("RGB")).getbbox())


if __name__ == "__main__":
    unittest.main()
