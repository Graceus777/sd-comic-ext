"""
Candidate scoring for multi-candidate panel selection.

Scores on three axes:
  1. Technical quality (sharpness, color, brightness) — PIL
  2. Aesthetic quality (saturation, contrast, detail) — PIL
  3. Content verification (tag overlap, face presence) — CLIP interrogation

Weights:
  With CLIP:    content 0.60, aesthetic 0.25, technical 0.15
  Without CLIP: aesthetic 0.60, technical 0.40
"""
import colorsys
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageStat


class PanelScorer:
    """Score candidate images and select the best one."""

    def __init__(self):
        self._interrogate_ok = None  # lazy check

    def select_best(
        self,
        candidate_paths: List[str],
        prompt: str,
        expects_face: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
        if not candidate_paths:
            return "", {}
        if len(candidate_paths) == 1:
            return candidate_paths[0], {}

        results = []
        for path in candidate_paths:
            score, breakdown = self._score(path, prompt, expects_face)
            results.append((path, score, breakdown))

        results.sort(key=lambda x: x[1], reverse=True)

        details = {}
        for path, score, breakdown in results:
            details[os.path.basename(path)] = {
                "total": round(score, 3),
                **{k: round(v, 3) for k, v in breakdown.items()},
            }
        return results[0][0], details

    def _score(self, path, prompt, expects_face):
        breakdown = {}
        breakdown["technical"] = self._score_technical(path)
        breakdown["aesthetic"] = self._score_aesthetic(path)

        content = self._score_content(path, prompt, expects_face)
        if content is not None:
            breakdown["content"] = content
            total = (
                breakdown["technical"] * 0.15
                + breakdown["aesthetic"] * 0.25
                + breakdown["content"] * 0.60
            )
        else:
            total = breakdown["technical"] * 0.40 + breakdown["aesthetic"] * 0.60
        return total, breakdown

    def _score_technical(self, path):
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            return 0.0
        if img.width > 512:
            ratio = 512 / img.width
            img = img.resize((512, int(img.height * ratio)))

        gray = img.convert("L")
        lap = gray.filter(ImageFilter.Kernel(
            size=(3, 3), kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
            scale=1, offset=128,
        ))
        sharpness = ImageStat.Stat(lap).var[0]
        sharp_score = min(sharpness / 1500.0, 1.0)

        stat = ImageStat.Stat(img)
        color_var = sum(stat.var) / 3.0
        color_score = min(color_var / 2500.0, 1.0)

        brightness = sum(stat.mean) / (3.0 * 255.0)
        bright_score = max(0.0, min(1.0, 1.0 - abs(brightness - 0.45) * 2.0))

        if color_var < 50:
            return 0.05
        return sharp_score * 0.40 + color_score * 0.30 + bright_score * 0.30

    def _score_aesthetic(self, path):
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            return 0.0

        small = img.resize((64, 64))
        sats = []
        for r, g, b in small.getdata():
            _, s, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            sats.append(s)
        avg_sat = sum(sats) / len(sats) if sats else 0
        sat_score = max(0.0, min(1.0, 1.0 - abs(avg_sat - 0.45) * 2.5))

        gray = img.convert("L")
        contrast = ImageStat.Stat(gray).stddev[0]
        contrast_score = min(contrast / 70.0, 1.0)

        edges = gray.filter(ImageFilter.FIND_EDGES)
        detail = ImageStat.Stat(edges).mean[0]
        detail_score = min(detail / 35.0, 1.0)

        return sat_score * 0.30 + contrast_score * 0.35 + detail_score * 0.35

    def _score_content(self, path, prompt, expects_face):
        caption = self._interrogate(path)
        if caption is None:
            return None

        caption_tags = {t.strip().lower() for t in caption.split(",") if t.strip()}
        prompt_tags = {t.strip().lower() for t in prompt.split(",") if t.strip()}

        skip = {
            "masterpiece", "best quality", "sharp focus", "highres",
            "absurdres", "detailed skin", "detailed face", "depth of field",
            "beautiful", "aesthetic", "1girl", "solo",
        }

        matches = checked = 0
        for ptag in prompt_tags:
            if ptag in skip or ptag.startswith("<lora:"):
                continue
            checked += 1
            if any(ptag in ctag or ctag in ptag for ctag in caption_tags):
                matches += 1

        coverage = matches / max(checked, 1)

        face_tags = {"1girl", "face", "portrait", "looking at viewer",
                     "girl", "close-up", "lips", "eyes"}
        has_face = bool(caption_tags & face_tags)

        penalty = 0.0
        if expects_face and not has_face:
            penalty += 0.20
        if not expects_face and has_face:
            penalty += 0.15
        if caption_tags & {"2girls", "multiple girls", "3girls", "crowd", "group"}:
            penalty += 0.25

        return max(0.0, min(1.0, coverage * 0.7 + 0.3 - penalty))

    def _interrogate(self, path):
        """Use A1111's built-in CLIP interrogator."""
        if self._interrogate_ok is False:
            return None

        try:
            from modules import shared
            img = Image.open(path).convert("RGB")
            caption = shared.interrogator.interrogate(img)
            self._interrogate_ok = True
            return caption
        except Exception:
            if self._interrogate_ok is None:
                self._interrogate_ok = False
                print("[CombinatorSD] CLIP interrogation unavailable, "
                      "using technical+aesthetic scoring only")
            return None
