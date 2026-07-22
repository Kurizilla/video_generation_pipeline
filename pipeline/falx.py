"""Wrappers de fal.ai con CANDADO DE COSTO + TIMEOUT. Sin secretos (usa FAL_KEY del entorno).

Un cuelgue/cola larga de fal se convierte en excepción (timeout), nunca en espera infinita.
Sin LOOP_ALLOW_PAID=1, `ensure_paid()` levanta PaidCallBlocked → el pipeline corre en dry-run sin gastar.
"""
from __future__ import annotations
import os, json, urllib.request, pathlib
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")  # <repo>/.env (secretos, gitignored)


class PaidCallBlocked(Exception):
    """Se levanta cuando se intenta una llamada paga sin LOOP_ALLOW_PAID=1."""


def paid_enabled() -> bool:
    return os.environ.get("LOOP_ALLOW_PAID") == "1"


def ensure_paid() -> None:
    if not paid_enabled():
        raise PaidCallBlocked("Llamada paga bloqueada. Seteá LOOP_ALLOW_PAID=1 para permitir gasto.")


def _client():
    import fal_client
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("Falta FAL_KEY en el entorno (ver .env.example).")
    return fal_client


def _find_url(obj, exts=(".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg")):
    """Busca recursivamente la primera URL de media en la respuesta de fal."""
    if isinstance(obj, dict):
        u = obj.get("url")
        if isinstance(u, str) and (u.lower().endswith(exts) or "media" in u):
            return u
        for v in obj.values():
            r = _find_url(v, exts)
            if r:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _find_url(v, exts)
            if r:
                return r
    return None


def upload(path) -> str:
    return _client().upload_file(str(path))


def download(url: str, dest) -> str:
    dest = pathlib.Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return str(dest)


def _subscribe(model, args, timeout):
    fal = _client()
    return fal.subscribe(model, arguments=args, with_logs=False,
                         start_timeout=timeout, client_timeout=int(timeout * 1.6))


# ---------------- Imagen ----------------
def image_gen(model, prompt, aspect="16:9", timeout=300) -> str | None:
    """Generación de imagen (sin refs). Devuelve URL."""
    ensure_paid()
    return _find_url(_subscribe(model, {"prompt": prompt, "aspect_ratio": aspect}, timeout))


def image_edit(model, prompt, ref_paths, aspect="16:9", timeout=300) -> str | None:
    """Edición/generación con imágenes de referencia (nano-banana / gemini edit). Devuelve URL."""
    ensure_paid()
    urls = [upload(p) for p in ref_paths]
    args = {"prompt": prompt, "image_urls": urls, "aspect_ratio": aspect}
    return _find_url(_subscribe(model + ("/edit" if not model.endswith("/edit") else ""), args, timeout))


def inpaint(model, prompt, image_path, mask_path, ref_path=None, strength=0.6, seed=None, timeout=300) -> str | None:
    """Inpainting con máscara (+ referencia opcional). Devuelve URL."""
    ensure_paid()
    args = {"prompt": prompt, "image_url": upload(image_path), "mask_url": upload(mask_path),
            "strength": strength, "num_inference_steps": 28}
    if ref_path is not None:
        args["reference_image_url"] = upload(ref_path); args["reference_strength"] = 0.85
    if seed is not None:
        args["seed"] = seed
    return _find_url(_subscribe(model, args, timeout))


# ---------------- Video (image-to-video, first + last frame) ----------------
def i2v(model, prompt, start_path, end_path, duration, resolution="1080p",
        aspect="16:9", cfg_scale=0.5, generate_audio=False, timeout=1500) -> str | None:
    """i2v con first+last frame. Maneja los nombres de param de Seedance vs Kling. Devuelve URL."""
    ensure_paid()
    su, eu = upload(start_path), upload(end_path)
    if "kling" in model:
        args = {"prompt": prompt, "start_image_url": su, "end_image_url": eu,
                "duration": str(duration), "generate_audio": generate_audio, "cfg_scale": cfg_scale}
    else:  # seedance u otros con image_url/end_image_url
        args = {"prompt": prompt, "image_url": su, "end_image_url": eu, "duration": str(duration),
                "resolution": resolution, "aspect_ratio": aspect, "generate_audio": generate_audio}
    return _find_url(_subscribe(model, args, timeout))
