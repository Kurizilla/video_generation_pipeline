"""Cliente LLM mínimo (REST, sin SDK) para tareas de TEXTO del pipeline —hoy: distribuir un guion en
prosa entre las tomas (una línea por toma, ajustada a la duración de cada una).

Proveedores (en orden de preferencia):
  1) Vertex AI / Gemini  — usa el login de gcloud (Application Default / usuario). El más potente
     disponible en el proyecto (auto-detecta entre una lista de candidatos; hoy: gemini-2.5-pro).
     Proyecto: GCP_PROJECT o `gcloud config get-value project`. Región: GCP_REGION (default us-central1).
  2) ANTHROPIC_API_KEY   3) OPENAI_API_KEY
Modelo forzable con GEMINI_MODEL / LLM_MODEL. Sin ninguna credencial, las funciones que lo usan se bloquean."""
import os, json, subprocess, urllib.request, urllib.error

# Candidatos Gemini de más a menos potente; el primero que responda 200 se cachea.
VERTEX_CANDIDATES = ["gemini-3-pro-preview", "gemini-2.5-pro", "gemini-1.5-pro-002"]
_vertex_model = [None]


# ---------------- gcloud helpers ----------------
def _gcloud(args, timeout=20):
    try:
        r = subprocess.run(["gcloud", *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""

def _gcp_project():
    return os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") \
        or (_gcloud(["config", "get-value", "project"]) or "").replace("(unset)", "")

def _gcp_token():
    return _gcloud(["auth", "print-access-token"]) or _gcloud(["auth", "application-default", "print-access-token"])


# ---------------- selección de proveedor ----------------
def vertex_available():
    return bool(_gcp_project())

def provider():
    if vertex_available(): return "vertex"
    if os.environ.get("ANTHROPIC_API_KEY"): return "anthropic"
    if os.environ.get("OPENAI_API_KEY"): return "openai"
    return None

def available(): return provider() is not None


# ---------------- completado ----------------
def complete(system, user, max_tokens=2048, temperature=0.4, images=None):
    """images (opcional): lista de {'mime','b64'} para prompts MULTIMODALES (solo Vertex/Gemini)."""
    p = provider()
    if not p:
        raise RuntimeError("Sin credencial LLM: logueate con gcloud (Vertex/Gemini) o poné "
                           "ANTHROPIC_API_KEY/OPENAI_API_KEY (ver .env.example).")
    if p == "vertex":  return _vertex(system, user, max_tokens, temperature, images)
    if images: raise RuntimeError("El análisis de imágenes requiere Vertex/Gemini (gcloud login).")
    if p == "anthropic": return _anthropic(system, user, max_tokens, temperature)
    return _openai(system, user, max_tokens, temperature)


def _post_json(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _vertex(system, user, max_tokens, temperature, images=None):
    proj = _gcp_project()
    if not proj: raise RuntimeError("No hay proyecto GCP (gcloud config set project … o GCP_PROJECT).")
    tok = _gcp_token()
    if not tok: raise RuntimeError("No pude obtener token de gcloud (¿corriste `gcloud auth login`?).")
    loc = os.environ.get("GCP_REGION", "us-central1")
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    forced = os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL")
    models = [forced] if forced else ([_vertex_model[0]] if _vertex_model[0] else VERTEX_CANDIDATES)
    parts = [{"text": user}]
    for im in (images or []):
        parts.append({"inlineData": {"mimeType": im["mime"], "data": im["b64"]}})
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
    last = None
    for mdl in models:
        url = f"https://{host}/v1/projects/{proj}/locations/{loc}/publishers/google/models/{mdl}:generateContent"
        try:
            d = _post_json(url, body, {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
            _vertex_model[0] = mdl
            parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(pt.get("text", "") for pt in parts)
        except urllib.error.HTTPError as e:
            last = f"{e.code}: {e.read().decode()[:200]}"
            if e.code in (400, 404) and not forced: continue     # modelo no disponible aquí → siguiente candidato
            raise RuntimeError(f"Vertex {mdl}: {last}")
        except Exception as e:
            last = str(e)[:200]
    raise RuntimeError(f"Vertex: ningún modelo Gemini disponible ({last})")


def _anthropic(system, user, max_tokens, temperature):
    d = _post_json("https://api.anthropic.com/v1/messages",
                   {"model": os.environ.get("LLM_MODEL", "claude-sonnet-5"), "max_tokens": max_tokens,
                    "temperature": temperature, "system": system, "messages": [{"role": "user", "content": user}]},
                   {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                    "content-type": "application/json"})
    return "".join(b.get("text", "") for b in d.get("content", []))


def _openai(system, user, max_tokens, temperature):
    d = _post_json("https://api.openai.com/v1/chat/completions",
                   {"model": os.environ.get("LLM_MODEL", "gpt-4o"), "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                   {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    return d["choices"][0]["message"]["content"]
