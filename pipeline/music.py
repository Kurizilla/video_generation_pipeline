"""Música de fondo ad-hoc con ElevenLabs Music (para mezclar BAJO la VO en el master).
Sin secretos: usa ELEVENLABS_API_KEY del entorno. Genera un instrumental del largo EXACTO del video."""
import os, json, urllib.request, pathlib

BASE = "https://api.elevenlabs.io/v1/music"


def theme_prompt(tema):
    return (f"Warm, hopeful and cinematic instrumental score for {tema}. Gentle piano and soft strings with "
            "subtle uplifting textures and light percussion; an optimistic, tender build that swells toward the "
            "end. Emotional, modern, unobtrusive so it sits UNDER a narrator's voice. No vocals, no lyrics, "
            "purely instrumental.")


def generate(prompt, duration_s, dest, model="music_v2"):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Falta ELEVENLABS_API_KEY (ver .env.example).")
    ms = max(3000, min(600000, round(float(duration_s) * 1000)))     # rango válido del endpoint
    body = {"prompt": prompt, "music_length_ms": ms, "model_id": model, "force_instrumental": True}
    req = urllib.request.Request(BASE + "?output_format=mp3_44100_128", data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    dest = pathlib.Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())
    if dest.stat().st_size < 2000:
        raise RuntimeError("respuesta de música vacía")
    return {"path": str(dest), "ms": ms}
