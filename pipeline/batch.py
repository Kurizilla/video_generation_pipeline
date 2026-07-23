"""Modo ACELERADO: genera KEYFRAMES y luego SHOTS de corrido, en paralelo, SIN gate manual entre etapas.
Aísla fallas por item (si una toma/keyframe falla, sigue con las demás) y reporta al final. Respeta el
candado de costo (sin LOOP_ALLOW_PAID no gasta: devuelve el plan/estimado). Reusa la misma lógica y modelos
de las etapas keyframes/shots (mismos guardrails first+last, seams compartidos, STYLE LOCK)."""
import concurrent.futures as cf
from . import falx, config, keyframes, shots


def _kf_one(project, stem, model):
    dest = project.keyframe_path(stem)
    if dest.is_file() and dest.stat().st_size > 10000:
        return stem, "cache", None
    spec = project.keyframes.get(stem)
    if not spec:
        return stem, "skip", "sin spec en project.json"
    prompt = (spec["prompt"] + " " + project.style).strip()
    refs = [r for r in (project.resolve_ref(x) for x in spec.get("refs", [])) if r.is_file()]
    try:
        url = falx.image_edit(model, prompt, refs, project.aspect) if refs else \
              falx.image_gen(model.replace("/edit", ""), prompt, project.aspect)
        if not url:
            return stem, "fail", "sin URL"
        dest.parent.mkdir(parents=True, exist_ok=True); falx.download(url, dest)
        return stem, "ok", None
    except Exception as e:
        return stem, "fail", f"{type(e).__name__}: {str(e)[:140]}"


def _shot_one(project, t, res):
    n = t["n"]; out = project.shot_path(n); model = shots._model_for(project, t)
    if out.is_file() and out.stat().st_size > 50000:
        return n, "cache", None
    start = project.keyframe_path(t["start"]); end = project.keyframe_path(t["end"])
    miss = [p.name for p in (start, end) if not p.is_file()]
    if miss:
        return n, "fail", f"faltan keyframes {miss}"
    try:
        url = falx.i2v(model, shots._prompt(project, t), start, end, t.get("duration", 5), res, project.aspect)
        if not url:
            return n, "fail", "sin URL"
        out.parent.mkdir(parents=True, exist_ok=True); falx.download(url, out)
        return n, "ok", None
    except Exception as e:
        return n, "fail", f"{type(e).__name__}: {str(e)[:140]}"


def plan(project):
    """Estimado del batch, SIN gastar."""
    uk = project.unique_keyframes()
    kf_model = project.models["image_hifi"]; vid_model = project.models["video"]
    res = config.DEFAULT_SHOT_RES
    kf_pending = [s for s in uk if not (project.keyframe_path(s).is_file() and project.keyframe_path(s).stat().st_size > 10000)]
    tomas = sorted(project.tomas, key=lambda x: x["n"])
    shot_pending = [t for t in tomas if not (project.shot_path(t["n"]).is_file() and project.shot_path(t["n"]).stat().st_size > 50000)]
    kf_cost = config.est_image_cost(kf_model, len(kf_pending))
    vid_cost = round(sum(config.est_video_cost(shots._model_for(project, t), res, t.get("duration", 5), 1) for t in shot_pending), 2)
    return {"keyframes_total": len(uk), "keyframes_pending": len(kf_pending),
            "shots_total": len(tomas), "shots_pending": len(shot_pending),
            "seconds": sum(int(t.get("duration", 5)) for t in shot_pending), "resolution": res,
            "kf_model": kf_model, "vid_model": vid_model,
            "est_kf_usd": kf_cost, "est_shots_usd": vid_cost, "est_total_usd": round(kf_cost + vid_cost, 2),
            "paid": falx.paid_enabled()}


def run(project, kf_workers=4, shot_workers=3, progress=None):
    """Corre keyframes (paralelo) y luego shots (paralelo). progress(dict) opcional para reportar avance."""
    def _emit(**kw):
        if progress: progress(kw)
    if not falx.paid_enabled():
        return {"dry": True, **plan(project)}
    keyframes.build_meta(project)
    kf_model = project.models["image_hifi"]; res = config.DEFAULT_SHOT_RES
    uk = project.unique_keyframes()

    # --- etapa 3: KEYFRAMES en paralelo ---
    kf_res = {}
    with cf.ThreadPoolExecutor(max_workers=kf_workers) as ex:
        futs = {ex.submit(_kf_one, project, s, kf_model): s for s in uk}
        for f in cf.as_completed(futs):
            stem, status, err = f.result(); kf_res[stem] = {"status": status, "error": err}
            _emit(phase="keyframes", stem=stem, status=status, done=len(kf_res), total=len(uk))
    kf_failed = [s for s, r in kf_res.items() if r["status"] in ("fail", "skip")]

    # --- etapa 4: SHOTS en paralelo (sin gate; usa los keyframes como guardrails) ---
    shots.build_meta(project)
    tomas = sorted(project.tomas, key=lambda x: x["n"])
    shot_res = {}
    with cf.ThreadPoolExecutor(max_workers=shot_workers) as ex:
        futs = {ex.submit(_shot_one, project, t, res): t["n"] for t in tomas}
        for f in cf.as_completed(futs):
            n, status, err = f.result(); shot_res[n] = {"status": status, "error": err}
            _emit(phase="shots", toma=n, status=status, done=len(shot_res), total=len(tomas))
    shots.build_meta(project)   # registra los crudos recién generados como v0 (para que el front los muestre)
    shot_failed = [{"toma": n, "error": r["error"]} for n, r in shot_res.items() if r["status"] == "fail"]

    ok_shots = sorted(n for n, r in shot_res.items() if r["status"] in ("ok", "cache"))
    return {"ok": True,
            "keyframes": {"total": len(uk), "ok": sum(1 for r in kf_res.values() if r["status"] == "ok"),
                          "cache": sum(1 for r in kf_res.values() if r["status"] == "cache"), "failed": kf_failed},
            "shots": {"total": len(tomas), "ok_or_cache": ok_shots, "failed": shot_failed,
                      "raw_dir": str((project.shot_path(1)).parent.relative_to(project.out))}}
