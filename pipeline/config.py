"""Config versionable (SIN secretos): modelos por defecto, precios estimados, timeouts.
Todo override-able por `project.json` (clave "models") o variables de entorno."""
from __future__ import annotations
import os, pathlib
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")  # carga <repo>/.env (gitignored)

# Endpoints fal por defecto (verificados jul-2026). Cambiar aquí o en project.json["models"].
DEFAULT_MODELS = {
    "image_multi":  "fal-ai/nano-banana-2/edit",              # regen completa multi-referencia (hasta ~14 refs)
    "image_hifi":   "fal-ai/gemini-3-pro-image-preview/edit", # alta fidelidad (2 refs) — usado en anclas/keyframes
    "inpaint":      "fal-ai/flux-general/inpainting",         # edición local por máscara + referencia
    "video":        "bytedance/seedance-2.0/image-to-video",  # i2v principal (first+last frame)
    "video_fallback": "fal-ai/kling-video/v3/pro/image-to-video",  # i2v sin filtro de likeness de ByteDance
}

# Precio estimado (USD) — solo para mostrar antes de gastar. VERIFICAR en fal.ai/pricing.
VIDEO_PRICE_PER_S = {"480p": 0.15, "720p": 0.3024, "1080p": 0.62, "4k": 1.5}
KLING_PRICE_PER_5S = 0.50
IMAGE_PRICE = {"fal-ai/nano-banana-2/edit": 0.06, "fal-ai/gemini-3-pro-image-preview/edit": 0.15,
               "fal-ai/flux-general/inpainting": 0.05}

# Timeouts (s) — un cuelgue de fal se corta y se reporta como error.
TIMEOUT_IMAGE = 300
TIMEOUT_VIDEO = 1500

# Voz por defecto (ElevenLabs). Override en project.json["voice_id"].
DEFAULT_VOICE_ID = "cgSgspJ2msm6clMCkdW9"   # "Jessica" — cálida/digna
TTS_MODEL = "eleven_v3"
TTS_FALLBACK = "eleven_multilingual_v2"

DEFAULT_SHOT_RES = os.environ.get("SHOT_RES", "1080p")


def models(project: dict) -> dict:
    m = dict(DEFAULT_MODELS)
    m.update(project.get("models", {}) or {})
    return m


def est_image_cost(model: str, n: int) -> float:
    return round(IMAGE_PRICE.get(model, 0.1) * n, 3)


def est_video_cost(model: str, res: str, dur, n: int) -> float:
    if "kling" in model:
        return round(KLING_PRICE_PER_5S * (int(dur) / 5) * n, 2)
    return round(VIDEO_PRICE_PER_S.get(res, 0.62) * int(dur) * n, 2)
