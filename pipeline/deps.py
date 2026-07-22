"""Grafo de dependencias KEYFRAME → VIDEO(s) + lógica STALE / propagación de empalme.
Editar/aceptar un keyframe marca STALE los videos que lo usan (un seam alimenta 2). No gasta."""
from __future__ import annotations
import json


def _vid(project):
    return json.loads(project.shots_meta.read_text()) if project.shots_meta.is_file() else {}

def _save_vid(project, m):
    project.shots_meta.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def graph(project):
    """stem -> {as_start:[tomas], as_end:[tomas], tomas:[...], is_seam:bool}."""
    shots, _ = project.seam_plan(); g = {}
    for n, s in shots.items():
        g.setdefault(s["start"], {"as_start": [], "as_end": []})["as_start"].append(n)
        g.setdefault(s["end"], {"as_start": [], "as_end": []})["as_end"].append(n)
    for stem, e in g.items():
        e["stem"] = stem; e["tomas"] = sorted(set(e["as_start"] + e["as_end"])); e["is_seam"] = len(e["tomas"]) > 1
    return g


def for_keyframe(project, stem):
    e = graph(project).get(stem, {"as_start": [], "as_end": [], "tomas": [], "is_seam": False, "stem": stem})
    return {"stem": stem, "as_start": e["as_start"], "as_end": e["as_end"], "tomas": e["tomas"], "is_seam": e["is_seam"]}


def explain(project, stem):
    i = for_keyframe(project, stem); parts = []
    if i["as_end"]:   parts.append("tomas " + ",".join(f"{n:02d}" for n in i["as_end"]) + " (END)")
    if i["as_start"]: parts.append("tomas " + ",".join(f"{n:02d}" for n in i["as_start"]) + " (START)")
    seam = " [EMPALME compartido]" if i["is_seam"] else ""
    return f"'{stem}'{seam} alimenta: " + " y ".join(parts) if parts else f"'{stem}' no alimenta ningún video."


def mark_stale(project, stem):
    """Marca STALE los videos que dependen del keyframe (los que ya tienen video)."""
    info = for_keyframe(project, stem); vm = _vid(project); aff = []
    for n in info["tomas"]:
        key = f"toma{n:02d}"
        if key in vm and vm[key].get("versions"):
            vm[key]["status"] = "stale"; aff.append(key)
    _save_vid(project, vm)
    info["marked_stale"] = aff; info["explain"] = explain(project, stem)
    return info


def to_regen(project):
    """Panel 'qué falta regenerar': videos STALE + pendientes (sin video)."""
    vm = _vid(project)
    return {"stale": [k for k, e in vm.items() if e.get("status") == "stale"],
            "pending": [k for k, e in vm.items() if not e.get("versions")]}


def assembly_ready(project):
    vm = _vid(project); tr = to_regen(project)
    approved = all(e.get("status") == "approved" for e in vm.values()) and len(vm) == len(project.tomas)
    return {"all_approved": approved, "stale": tr["stale"], "pending": tr["pending"],
            "ready": approved and not tr["stale"]}
