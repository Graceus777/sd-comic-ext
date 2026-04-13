"""
Generation engine using A1111's internal processing.

Replaces the HTTP API client — calls modules.processing directly
for txt2img and img2img, returning PIL Images with no base64 overhead.
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


def _get_sd_model():
    """Get the currently loaded SD model."""
    from modules import shared
    return shared.sd_model


def _check_interrupted():
    """Check if the user has requested an interrupt."""
    from modules import shared
    return shared.state.interrupted


def _set_job(job_name: str):
    """Set the current job name for A1111's progress display."""
    try:
        from modules import shared
        shared.state.job = job_name
    except Exception:
        pass


def generate_txt2img(
    prompt: str,
    negative_prompt: str = "",
    steps: int = 27,
    sampler_name: str = "Euler a",
    cfg_scale: float = 6.0,
    width: int = 1024,
    height: int = 1280,
    seed: int = -1,
    batch_size: int = 1,
    enable_hr: bool = False,
    hr_scale: float = 1.5,
    hr_upscaler: str = "Latent",
    denoising_strength: float = 0.5,
    enable_adetailer: bool = False,
    adetailer_settings: Optional[Dict] = None,
    controlnet_args: Optional[Dict] = None,
    output_dir: str = "generated_images",
    custom_filename: str = "image",
) -> Tuple[bool, str, List[str], List[Image.Image]]:
    """
    Generate images via txt2img using A1111's internal processing.

    Returns:
        (success, message, list_of_saved_filepaths, list_of_pil_images)
    """
    from modules import processing, shared

    os.makedirs(output_dir, exist_ok=True)

    p = processing.StableDiffusionProcessingTxt2Img(
        sd_model=shared.sd_model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        steps=steps,
        sampler_name=sampler_name,
        cfg_scale=cfg_scale,
        width=width,
        height=height,
        seed=seed,
        batch_size=batch_size,
        outpath_samples=output_dir,
        outpath_grids=output_dir,
    )

    if enable_hr:
        p.enable_hr = True
        p.hr_scale = hr_scale
        p.hr_upscaler_name = hr_upscaler
        p.denoising_strength = denoising_strength

    # ADetailer via alwayson_scripts
    if enable_adetailer:
        _attach_adetailer(p, adetailer_settings)

    # ControlNet via alwayson_scripts
    if controlnet_args:
        _attach_controlnet(p, controlnet_args)

    try:
        result = processing.process_images(p)
    except Exception as e:
        return False, f"Generation error: {e}", [], []

    if not result.images:
        return False, "No images generated", [], []

    images_out = list(result.images[:batch_size])
    info_text = getattr(result, "info", None)

    saved_files = _save_images(images_out, output_dir, custom_filename, info_text=info_text)
    _mirror_to_default_output(images_out, "txt2img", info_text=info_text)

    return (
        True,
        f"Generated {len(saved_files)} image(s)",
        saved_files,
        images_out,
    )


def generate_img2img(
    init_image: Image.Image,
    prompt: str,
    negative_prompt: str = "",
    steps: int = 27,
    sampler_name: str = "Euler a",
    cfg_scale: float = 6.0,
    width: int = 1024,
    height: int = 1280,
    seed: int = -1,
    batch_size: int = 1,
    denoising_strength: float = 0.75,
    resize_mode: int = 0,
    enable_adetailer: bool = False,
    adetailer_settings: Optional[Dict] = None,
    controlnet_args: Optional[Dict] = None,
    output_dir: str = "generated_images",
    custom_filename: str = "img2img",
) -> Tuple[bool, str, List[str], List[Image.Image]]:
    """
    Generate images via img2img using A1111's internal processing.

    Returns:
        (success, message, list_of_saved_filepaths, list_of_pil_images)
    """
    from modules import processing, shared

    os.makedirs(output_dir, exist_ok=True)

    p = processing.StableDiffusionProcessingImg2Img(
        sd_model=shared.sd_model,
        init_images=[init_image],
        prompt=prompt,
        negative_prompt=negative_prompt,
        steps=steps,
        sampler_name=sampler_name,
        cfg_scale=cfg_scale,
        width=width,
        height=height,
        seed=seed,
        batch_size=batch_size,
        denoising_strength=denoising_strength,
        resize_mode=resize_mode,
        outpath_samples=output_dir,
        outpath_grids=output_dir,
    )

    if enable_adetailer:
        _attach_adetailer(p, adetailer_settings)

    if controlnet_args:
        _attach_controlnet(p, controlnet_args)

    try:
        result = processing.process_images(p)
    except Exception as e:
        return False, f"Generation error: {e}", [], []

    if not result.images:
        return False, "No images generated", [], []

    images_out = list(result.images[:batch_size])
    info_text = getattr(result, "info", None)

    saved_files = _save_images(images_out, output_dir, custom_filename, info_text=info_text)
    _mirror_to_default_output(images_out, "img2img", info_text=info_text)

    return (
        True,
        f"Generated {len(saved_files)} image(s)",
        saved_files,
        images_out,
    )


def interrogate_clip(image: Image.Image) -> Optional[str]:
    """Get CLIP tags for an image using A1111's built-in interrogator."""
    try:
        from modules import shared
        interrogator = shared.interrogator
        caption = interrogator.interrogate(image.convert("RGB"))
        return caption
    except Exception:
        return None


def _attach_adetailer(p, settings: Optional[Dict] = None):
    """Attach ADetailer script args to a processing object."""
    try:
        from modules import scripts as scripts_module

        ad_args = {
            "ad_model": "face_yolov8n.pt",
            "ad_mask_k_largest": 1,
        }
        if settings:
            ad_args.update({k: v for k, v in settings.items() if v is not None})

        for script in scripts_module.scripts_txt2img.alwayson_scripts:
            if script.title().lower().startswith("adetailer"):
                args_from = script.args_from
                args_to = script.args_to
                if hasattr(p, "script_args"):
                    while len(p.script_args) < args_to:
                        p.script_args.append(None)
                    p.script_args[args_from] = True      # ad_enable
                    p.script_args[args_from + 1] = False  # skip_img2img
                    p.script_args[args_from + 2] = ad_args
                break
    except Exception:
        pass


def list_adetailer_models() -> List[str]:
    """Return available ADetailer detector models."""
    defaults = [
        "face_yolov8n.pt",
        "face_yolov8s.pt",
        "hand_yolov8n.pt",
        "person_yolov8n-seg.pt",
        "mediapipe_face_full",
        "mediapipe_face_short",
        "mediapipe_face_mesh",
    ]
    try:
        # Try to get live list from ADetailer extension
        from adetailer.ultralytics import get_models
        live = get_models()
        if live:
            return live
    except Exception:
        pass
    try:
        # Fallback: scan ADetailer's model directory
        import pathlib
        from modules import paths as webui_paths
        ad_model_dir = pathlib.Path(webui_paths.models_path) / "adetailer"
        if ad_model_dir.is_dir():
            found = sorted(f.name for f in ad_model_dir.glob("*.pt"))
            if found:
                return found
    except Exception:
        pass
    return defaults


def _attach_controlnet(p, cn_args: Dict):
    """Attach ControlNet args to a processing object."""
    try:
        from modules import scripts as scripts_module

        for script in scripts_module.scripts_txt2img.alwayson_scripts:
            if "controlnet" in script.title().lower():
                args_from = script.args_from
                if hasattr(p, "script_args"):
                    while len(p.script_args) < args_from + 1:
                        p.script_args.append(None)
                    # ControlNet expects a list of unit dicts
                    unit = {
                        "enabled": True,
                        "image": cn_args.get("image"),
                        "module": cn_args.get("preprocessor", "none"),
                        "model": cn_args.get("model", ""),
                        "weight": cn_args.get("weight", 1.0),
                        "guidance_start": cn_args.get("guidance_start", 0.0),
                        "guidance_end": cn_args.get("guidance_end", 1.0),
                        "pixel_perfect": True,
                        "control_mode": cn_args.get("control_mode", "Balanced"),
                        "resize_mode": "Just Resize",
                    }
                    p.script_args[args_from] = [unit]
                break
    except Exception:
        pass


def _save_images(
    images: List[Image.Image],
    output_dir: str,
    custom_filename: str,
    info_text: Optional[str] = None,
) -> List[str]:
    """Save PIL images to disk with generation metadata embedded in PNG info."""
    from PIL import PngImagePlugin
    os.makedirs(output_dir, exist_ok=True)
    saved = []
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for idx, img in enumerate(images):
        if len(images) > 1:
            filename = f"{timestamp}_{custom_filename}_{idx + 1}.png"
        else:
            filename = f"{timestamp}_{custom_filename}.png"

        filepath = os.path.abspath(os.path.join(output_dir, filename))
        filepath = filepath.replace("\\", "/")  # Normalize for Gradio
        try:
            if info_text:
                pnginfo = PngImagePlugin.PngInfo()
                pnginfo.add_text("parameters", info_text)
                img.save(filepath, format="PNG", pnginfo=pnginfo)
            else:
                img.save(filepath, format="PNG")
            saved.append(filepath)
        except Exception as e:
            print(f"[CombinatorSD] Failed to save image {idx}: {e}")

    return saved


def _mirror_to_default_output(
    images: List[Image.Image],
    mode: str,
    info_text: Optional[str] = None,
):
    """
    Also save images to A1111's configured default output directory so they
    appear in the gallery and retain full PNG metadata for inspection.

    mode: "txt2img" or "img2img"
    Silently skips if the output dir is not configured or unavailable.
    """
    try:
        from modules import shared
        from PIL import PngImagePlugin

        if mode == "txt2img":
            outdir = getattr(shared.opts, "outdir_txt2img_samples", "")
        else:
            outdir = getattr(shared.opts, "outdir_img2img_samples", "")

        if not outdir:
            return

        # A1111 uses date sub-dirs; mirror that convention
        date_subdir = datetime.now().strftime("%Y-%m-%d")
        dest = os.path.join(outdir, date_subdir)
        os.makedirs(dest, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for idx, img in enumerate(images):
            suffix = f"_{idx + 1}" if len(images) > 1 else ""
            fname = f"{timestamp}_comic{suffix}.png"
            fpath = os.path.join(dest, fname)
            try:
                if info_text:
                    pnginfo = PngImagePlugin.PngInfo()
                    pnginfo.add_text("parameters", info_text)
                    img.save(fpath, format="PNG", pnginfo=pnginfo)
                else:
                    img.save(fpath, format="PNG")
            except Exception as e:
                print(f"[CombinatorSD] Mirror save failed: {e}")
    except Exception:
        pass  # Never break generation over a mirror-save failure
