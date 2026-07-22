"""Etapa 4: SHOTS (image-to-video, first+last frame). Anima cada toma start_ref→end_ref (los keyframes
son los guardrails; en seams compartidos el END de N = START de N+1). Seedance por default; el
video_fallback (Kling) se usa en content_blocked_tomas. Escribe shots_meta.json. Dry-run sin gasto."""
from __future__ import annotations
import json
from . import falx, config


def _prompt(project, t):
    return (t["motion"] + (" The camera is rigidly locked and static." if t.get("static") else "")
            + " " + project.style).strip()


def _model_for(project, t):
    return project.models["video_fallback"] if t["n"] in project.content_blocked else project.models["video"]


def build_meta(project):
    m = {}
    old = json.loads(project.shots_meta.read_text()) if project.shots_meta.is_file() else {}
    for t in sorted(project.tomas, key=lambda x: x["n"]):
        n = t["n"]; key = f"toma{n:02d}"; model = _model_for(project, t)
        blocked = n in project.content_blocked
        entry = {"toma": n, "key": key, "model": model, "content_blocked": blocked,
                 "prompt": _prompt(project, t),
                 "params": {"duration": str(t.get("duration", 5)), "resolution": config.DEFAULT_SHOT_RES,
                            "aspect_ratio": project.aspect, "static": bool(t.get("static")),
                            "supports": (["duration", "cfg_scale"] if blocked else ["duration", "resolution"])},
                 "start_ref": str(project.keyframe_path(t["start"]).relative_to(project.out)),
                 "end_ref": str(project.keyframe_path(t["end"]).relative_to(project.out)),
                 "vo": t.get("vo", ""), "versions": [], "current": 0, "status": "pending",
                 "candidates": [], "last_error": None}
        if key in old:
            for k in ("versions", "current", "status", "candidates", "last_error"):
                entry[k] = old[key].get(k, entry[k])
        if not entry["versions"] and project.shot_path(n).is_file():
            entry["versions"] = [{"v": 0, "path": f"shots_raw/{key}.mp4", "source": "gen", "note": "original", "ts": None}]
            entry["status"] = "generated"
        m[key] = entry
    project.shots_meta.write_text(json.dumps(m, ensure_ascii=False, indent=2))
    return m


def run(project, which=None):
    dry = not falx.paid_enabled(); res = config.DEFAULT_SHOT_RES
    build_meta(project)
    tomas = [t for t in sorted(project.tomas, key=lambda x: x["n"]) if not which or t["n"] in which]
    total_s = sum(int(t.get("duration", 5)) for t in tomas)
    print(f"== shots :: {'DRY (no gasta)' if dry else 'PAGA'} :: {res} :: {len(tomas)} tomas :: {total_s}s ==")
    results = {}
    for t in tomas:
        n = t["n"]; out = project.shot_path(n); model = _model_for(project, t)
        if out.is_file() and out.stat().st_size > 50000:
            print(f"  [cache] toma{n:02d}"); results[n] = "cache"; continue
        start = project.keyframe_path(t["start"]); end = project.keyframe_path(t["end"])
        eng = "kling" if "kling" in model else "seedance"
        if dry:
            miss = [p.name for p in (start, end) if not p.is_file()]
            cost = config.est_video_cost(model, res, t.get("duration", 5), 1)
            print(f"  [DRY]  toma{n:02d} {t.get('duration',5)}s {eng} ~${cost}"
                  + (f"  FALTAN keyframes={miss}" if miss else "") + ("  [ESTÁTICA]" if t.get("static") else ""))
            results[n] = "dry"; continue
        try:
            url = falx.i2v(model, _prompt(project, t), start, end, t.get("duration", 5), res, project.aspect)
            if url:
                falx.download(url, out); print(f"  [OK]   toma{n:02d} ({eng})"); results[n] = "ok"
            else:
                print(f"  [FAIL] toma{n:02d} sin URL"); results[n] = "fail"
        except Exception as e:
            print(f"  [FAIL] toma{n:02d} {type(e).__name__}: {str(e)[:140]}"); results[n] = "fail"
    return results
