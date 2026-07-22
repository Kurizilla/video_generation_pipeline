"""TTS ElevenLabs (REST directo). Sin secretos: usa ELEVENLABS_API_KEY del entorno."""
from __future__ import annotations
import os, json, urllib.request, pathlib
from . import config

BASE = "https://api.elevenlabs.io/v1/text-to-speech"


def synth(text, dest, voice_id, model=config.TTS_MODEL, fallback=config.TTS_FALLBACK):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Falta ELEVENLABS_API_KEY (ver .env.example).")
    dest = pathlib.Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for m in (model, fallback):
        body = {"text": text, "model_id": m,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.25}}
        req = urllib.request.Request(
            f"{BASE}/{voice_id}?output_format=mp3_44100_128",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                dest.write_bytes(r.read())
            return {"model": m, "path": str(dest)}
        except Exception as e:
            last = e
    raise last
