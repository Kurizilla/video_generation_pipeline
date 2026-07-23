"""Cliente LLM mínimo (REST, sin SDK) para tareas de TEXTO del pipeline —hoy: distribuir un guion en
prosa entre las tomas (una línea por toma, ajustada a la duración de cada una). Sin secretos: usa
ANTHROPIC_API_KEY u OPENAI_API_KEY del entorno. Modelo configurable con LLM_MODEL. Sin la llave, las
funciones que lo usan quedan bloqueadas (no hay fallback silencioso)."""
import os, json, urllib.request


def provider():
    if os.environ.get("ANTHROPIC_API_KEY"): return "anthropic"
    if os.environ.get("OPENAI_API_KEY"): return "openai"
    return None


def available(): return provider() is not None


def complete(system, user, max_tokens=1500, temperature=0.4):
    p = provider()
    if not p:
        raise RuntimeError("Falta ANTHROPIC_API_KEY u OPENAI_API_KEY (ver .env.example).")
    if p == "anthropic":
        model = os.environ.get("LLM_MODEL", "claude-sonnet-5")
        body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                "system": system, "messages": [{"role": "user", "content": user}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                     headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                                              "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
        return "".join(b.get("text", "") for b in d.get("content", []))
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"]
