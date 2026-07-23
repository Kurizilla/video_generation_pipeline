"""Etapa 3: KEYFRAMES (seam-aware). Genera cada keyframe ÚNICO una sola vez; los seams compartidos
(end_ref[N] == start_ref[N+1]) alimentan dos tomas. Escribe keyframes_meta.json (para el editor + deps).
Lee project.keyframes = {stem: {prompt, refs}}. Dry-run sin gasto por default."""
from __future__ import annotations
import json
from . import falx, config


def build_meta(project):
    """Manifiesto por keyframe: prompt original + refs + modelo + versiones (para editor no destructivo)."""
    meta = {}
    old = json.loads(project.kf_meta.read_text()) if project.kf_meta.is_file() else {}
    for stem in project.unique_keyframes():
        spec = project.keyframes.get(stem, {"prompt": "", "refs": []})
        refs = [r for r in spec.get("refs", [])]
        model = project.models["image_hifi"] if refs else project.models["image_hifi"]
        relfile = str(project.keyframe_path(stem).relative_to(project.out))
        entry = {"stem": stem, "file": relfile,
                 "prompt": (spec["prompt"] + " " + project.style).strip(), "refs": refs,
                 "model": model, "versions": [], "current": 0, "last_error": None}
        if stem in old:
            entry["versions"] = old[stem].get("versions", []); entry["current"] = old[stem].get("current", 0)
        if not entry["versions"] and project.keyframe_path(stem).is_file():   # solo v0 si la imagen existe
            entry["versions"] = [{"v": 0, "path": relfile, "source": "gen", "note": "original", "ts": None}]
        meta[stem] = entry
    project.kf_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def run(project, only=None):
    dry = not falx.paid_enabled()
    model = project.models["image_hifi"]
    build_meta(project)
    stems = project.unique_keyframes()
    seams = [s for s in stems if s.startswith("seam")]
    print(f"== keyframes :: {'DRY (no gasta)' if dry else 'PAGA'} :: {len(stems)} únicos "
          f"({len(seams)} seams compartidos) :: {model} ==")
    results = {}
    for stem in stems:
        if only and stem not in only:
            continue
        dest = project.keyframe_path(stem)
        if dest.is_file() and dest.stat().st_size > 10000:
            print(f"  [cache] {stem}"); results[stem] = "cache"; continue
        spec = project.keyframes.get(stem)
        if not spec:
            print(f"  [skip]  {stem} sin spec en project.json"); results[stem] = "skip"; continue
        prompt = (spec["prompt"] + " " + project.style).strip()
        refs = [project.resolve_ref(r) for r in spec.get("refs", [])]
        missing = [r.name for r in refs if not r.is_file()]
        refs = [r for r in refs if r.is_file()]
        if dry:
            tag = f"refs={[r.name for r in refs]}" + (f" FALTAN={missing}" if missing else "")
            print(f"  [DRY]  {stem}  {tag}"); results[stem] = "dry"; continue
        try:
            url = falx.image_edit(model, prompt, refs, project.aspect) if refs else \
                  falx.image_gen(model.replace('/edit', ''), prompt, project.aspect)
            if url:
                falx.download(url, dest); print(f"  [OK]   {stem}"); results[stem] = "ok"
            else:
                print(f"  [FAIL] {stem} sin URL"); results[stem] = "fail"
        except Exception as e:
            print(f"  [FAIL] {stem} {type(e).__name__}: {str(e)[:140]}"); results[stem] = "fail"
    return results
