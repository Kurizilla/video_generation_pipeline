"""Etapas 1-2: PERSONAJES + SETS → genera las hojas de anclaje (placa de estilo, personajes, sets).
Lee project.anchors = {id: {prompt, refs}}. Idempotente. Dry-run sin gasto por default."""
from __future__ import annotations
from . import falx, config


def run(project, only=None):
    dry = not falx.paid_enabled()
    model = project.models["image_hifi"]
    results = {}
    print(f"== anchors :: {'DRY (no gasta)' if dry else 'PAGA'} :: {model} ==")
    for aid, spec in project.anchors.items():
        if only and aid not in only:
            continue
        dest = project.anchor_path(aid)
        if dest.is_file() and dest.stat().st_size > 10000:
            print(f"  [cache] {aid}"); results[aid] = "cache"; continue
        prompt = (spec["prompt"] + " " + project.style).strip()
        refs = [project.resolve_ref(r) for r in spec.get("refs", [])]
        refs = [r for r in refs if r.is_file()]
        if dry:
            print(f"  [DRY]  {aid}  refs={[r.name for r in refs]}  ~${config.est_image_cost(model,1)}")
            results[aid] = "dry"; continue
        try:
            url = (falx.image_edit(model, prompt, refs, project.aspect) if refs
                   else falx.image_gen(model.replace('/edit', ''), prompt, project.aspect))
            if url:
                falx.download(url, dest); print(f"  [OK]   {aid}"); results[aid] = "ok"
            else:
                print(f"  [FAIL] {aid} sin URL"); results[aid] = "fail"
        except Exception as e:
            print(f"  [FAIL] {aid} {type(e).__name__}: {str(e)[:140]}"); results[aid] = "fail"
    return results
