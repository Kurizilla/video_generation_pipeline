"""API del pipeline (FastAPI) — backend del front React. Opera todas las etapas de UN proyecto:
navegar anchors/keyframes/tomas, disparar generaciones por etapa, editor de keyframes (A/B), regen de
video por plano, grafo keyframe→video con STALE, y el GO final (assemble). Guarda la FAL_KEY en el backend
(el navegador nunca la ve). Regen de imagen/video ASÍNCRONA (job + polling). Sin LOOP_ALLOW_PAID=1 → dry.
"""
import json, threading, uuid, pathlib
from . import deps, editing, anchors, keyframes, shots, assemble, falx

_JOBS = {}; _LOCK = threading.Lock(); _SEQ = [0]


def _mk_job(kind, label, total):
    with _LOCK:
        _SEQ[0] += 1
        jid = uuid.uuid4().hex[:12]
        _JOBS[jid] = {"variants": [], "errors": [], "done": False, "total": total,
                      "kind": kind, "label": label, "seq": _SEQ[0]}
    return jid


def _view_tomas(project):
    g = deps.graph(project); vm = editing._load(project.shots_meta)
    def seam(stem): return g.get(stem, {}).get("is_seam", False)
    out = []
    for t in sorted(project.tomas, key=lambda x: x["n"]):
        key = f"toma{t['n']:02d}"; e = vm.get(key, {})
        out.append({"n": t["n"], "key": key, "title": t.get("title", ""), "model": e.get("model"),
                    "content_blocked": t["n"] in project.content_blocked,
                    "video_status": e.get("status", "pending"), "has_video": bool(e.get("versions")),
                    "start": {"stem": t["start"], "is_seam": seam(t["start"])},
                    "end": {"stem": t["end"], "is_seam": seam(t["end"])}})
    return out


def _worker(jid, fn, plan, n):
    # Las N variantes se generan EN PARALELO (cada llamada a fal es independiente y libera el GIL en la
    # espera de red). Antes iban en serie, por eso pedir 2-3 variantes tardaba 2-3x. Los distintos jobs
    # (keyframes/tomas) ya corrían en paralelo, un thread por job.
    from concurrent.futures import ThreadPoolExecutor
    def _one(i):
        try:
            r = fn(plan, i)                                   # descarga + registra en _tmp al completar
            with _LOCK: _JOBS[jid]["variants"].append(r)
        except Exception as ex:
            with _LOCK: _JOBS[jid]["errors"].append(f"{type(ex).__name__}: {str(ex)[:180]}")
    with ThreadPoolExecutor(max_workers=max(1, n)) as ex:
        list(ex.map(_one, range(n)))
    with _LOCK: _JOBS[jid]["done"] = True
    return _JOBS[jid]["errors"]


class ActiveProject:
    """Proxy al proyecto ACTIVO. Todos los endpoints operan sobre este objeto; cambiar de proyecto solo
    intercambia el Project subyacente (._p), así el front puede seleccionar sin reiniciar el server."""
    def __init__(self, initial):
        object.__setattr__(self, "_p", initial)
        object.__setattr__(self, "root", initial.dir.parent)   # carpeta projects/
    def _switch(self, name):
        from . import project as prj
        object.__setattr__(self, "_p", prj.load(self.root / name))
    def __getattr__(self, k): return getattr(object.__getattribute__(self, "_p"), k)


def _list_projects(root):
    return sorted(d.name for d in pathlib.Path(root).iterdir() if (d / "project.json").is_file())


def build_app(project):
    import pathlib
    from fastapi import FastAPI, Body
    from fastapi.responses import FileResponse, Response
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(title=f"video-pipeline · {project.name}")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/out/{path:path}")
    def serve_out(path):
        # sirve assets generados bajo project.out; sigue symlinks (assets enlazados) con guard anti-traversal
        if ".." in path.split("/"):
            return Response(status_code=403)
        p = project.out / path
        if not p.is_file():   # is_file() resuelve symlinks
            return Response(status_code=404)
        return FileResponse(str(p))

    @app.get("/api/project")
    def project_info():
        return {"name": project.name, "aspect": project.aspect, "paid": falx.paid_enabled(),
                "anchors": list(project.anchors), "tomas": len(project.tomas)}

    # -------- multi-proyecto (selector del front) --------
    @app.get("/api/projects")
    def projects_list():
        names = _list_projects(project.root)
        return {"projects": [{"name": n, "active": n == project.name} for n in names], "active": project.name}

    @app.post("/api/projects/select")
    def projects_select(body: dict = Body(...)):
        name = body.get("name", "")
        if not (project.root / name / "project.json").is_file():
            return {"error": f"proyecto '{name}' no existe"}
        if isinstance(project, ActiveProject):
            project._switch(name)
            (project.root / ".active").write_text(name)   # persiste la selección entre reinicios
        return {"ok": True, "active": project.name}

    @app.post("/api/projects/create")
    def projects_create(body: dict = Body(...)):
        name = (body.get("name") or "").strip()
        if not name or "/" in name or name.startswith("."):
            return {"error": "nombre inválido"}
        d = project.root / name
        if (d / "project.json").is_file():
            return {"error": f"'{name}' ya existe"}
        (d / "captures").mkdir(parents=True, exist_ok=True)
        cfg = {"name": name, "aspect_ratio": body.get("aspect", "16:9"), "style": body.get("style", ""),
               "voice_id": body.get("voice_id", ""), "content_blocked_tomas": [],
               "anchors": {}, "keyframes": {}, "tomas": []}
        (d / "project.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
        return {"ok": True, "name": name}

    @app.get("/api/tomas")
    def tomas(): return _view_tomas(project)

    @app.get("/api/kf/{stem}")
    def kf_meta(stem):
        e = editing._load(project.kf_meta).get(stem)
        if not e: return {"error": "no existe"}
        imgs = []
        for r in e.get("refs", []):
            p = project.resolve_ref(r)
            try: rel = str(p.relative_to(project.out)); under = True
            except ValueError: rel, under = None, False
            imgs.append({"ref": r, "out": rel, "under_out": under, "exists": p.is_file()})
        return {**e, "ref_imgs": imgs}

    @app.get("/api/vid/{key}")
    def vid_meta(key): return editing._load(project.shots_meta).get(key, {"error": "no existe"})

    @app.get("/api/deps/graph")
    def dgraph(): return deps.graph(project)
    @app.get("/api/deps/to-regen")
    def dregen(): return deps.to_regen(project)
    @app.get("/api/deps/for/{stem}")
    def dfor(stem): return deps.for_keyframe(project, stem)
    @app.get("/api/assembly-ready")
    def aready(): return deps.assembly_ready(project)

    # -------- keyframe edit (async) --------
    @app.post("/api/kf/regen")
    def kf_regen(body: dict = Body(...)):
        n = int(body.get("num_variants", 2))
        plan = editing.kf_prep(project, body["stem"], body.get("mode", "A"), body.get("comment", ""),
                               body.get("instruction", ""), body.get("ref_images", []), body.get("hifi", False),
                               body.get("strength", 0.6), body.get("mask_png"), n, prompt=body.get("prompt"),
                               base_refs=body.get("base_refs"))
        if "error" in plan: return plan
        if not falx.paid_enabled(): return {"dry": True, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}
        jid = _mk_job("kf", body["stem"], n)
        threading.Thread(target=lambda: (_worker(jid, lambda pl, i: editing.kf_regen_one(project, pl, i), plan, n),
                                         editing.kf_set_error(project, body["stem"], _JOBS[jid]["errors"])), daemon=True).start()
        return {"job_id": jid, "total": n, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}

    @app.get("/api/kf/status/{jid}")
    def kf_status(jid): return _JOBS.get(jid, {"error": "job desconocido"})
    @app.get("/api/kf/variants/{stem}")
    def kf_vars(stem): return {"variants": editing.kf_variants(project, stem)}
    @app.post("/api/kf/accept")
    def kf_acc(body: dict = Body(...)):
        r = editing.kf_accept(project, body["stem"], body["variant_path"], body.get("note", ""))
        if r.get("ok"): r["deps"] = deps.mark_stale(project, body["stem"])
        return r
    @app.post("/api/kf/revert")
    def kf_rev(body: dict = Body(...)):
        r = editing.kf_revert(project, body["stem"], body["v"])
        if r.get("ok"): r["deps"] = deps.mark_stale(project, body["stem"])
        return r

    # -------- video edit (async) --------
    @app.post("/api/vid/regen")
    def vid_regen(body: dict = Body(...)):
        n = int(body.get("num_variants", 2))
        plan = editing.vid_prep(project, body["key"], body.get("comment", ""), body.get("overrides", {}), n)
        if "error" in plan: return plan
        if not falx.paid_enabled(): return {"dry": True, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}
        jid = _mk_job("vid", body["key"], n)
        threading.Thread(target=lambda: (_worker(jid, lambda pl, i: editing.vid_regen_one(project, pl, i), plan, n),
                                         editing.vid_set_error(project, body["key"], _JOBS[jid]["errors"])), daemon=True).start()
        return {"job_id": jid, "total": n, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}

    @app.get("/api/vid/status/{jid}")
    def vid_status_job(jid): return _JOBS.get(jid, {"error": "job desconocido"})
    @app.get("/api/vid/variants/{key}")
    def vid_vars(key): return {"variants": editing.vid_variants(project, key)}

    # -------- cola global de jobs (para el tracker del front) --------
    @app.get("/api/jobs")
    def jobs():
        with _LOCK:
            items = [{"jid": j, "kind": v["kind"], "label": v.get("label", ""), "total": v["total"],
                      "done_count": len(v["variants"]), "done": v["done"], "errors": v["errors"],
                      "seq": v.get("seq", 0)} for j, v in _JOBS.items()]
        items.sort(key=lambda x: x["seq"], reverse=True)   # más reciente primero
        return {"jobs": items}

    @app.post("/api/jobs/clear")
    def jobs_clear():
        with _LOCK:
            gone = [j for j, v in _JOBS.items() if v["done"]]
            for j in gone: _JOBS.pop(j, None)
        return {"ok": True, "cleared": len(gone)}
    @app.post("/api/vid/accept")
    def vid_acc(body: dict = Body(...)): return editing.vid_accept(project, body["key"], body["variant_path"], body.get("note", ""))
    @app.post("/api/vid/revert")
    def vid_rev(body: dict = Body(...)): return editing.vid_revert(project, body["key"], body["v"])
    @app.post("/api/vid/set-status")
    def vid_st(body: dict = Body(...)): return editing.vid_set_status(project, body["key"], body["status"])

    # -------- disparar etapas / GO --------
    @app.post("/api/stage/{name}")
    def run_stage(name, body: dict = Body(default={})):
        if name == "anchors": return {"result": anchors.run(project, only=body.get("only"))}
        if name == "keyframes": return {"result": keyframes.run(project, only=body.get("only"))}
        if name == "shots": return {"result": shots.run(project, which=body.get("tomas"))}
        return {"error": "etapa desconocida"}
    @app.post("/api/assemble")
    def go(body: dict = Body(default={})): return assemble.run(project, music=body.get("music"))

    # -------- reemplazo MANUAL por archivo local (upload) --------
    import time as _t, shutil as _sh
    from fastapi import UploadFile, File, Form

    @app.post("/api/kf/upload")
    async def kf_upload(stem: str = Form(...), file: UploadFile = File(...)):
        tmp = project.out / "keyframes" / "_tmp"; tmp.mkdir(parents=True, exist_ok=True)
        dest = tmp / f"{stem}.upload.{int(_t.time()*1000)}.png"; dest.write_bytes(await file.read())
        r = editing.kf_accept(project, stem, str(dest.relative_to(project.out)), note="reemplazo manual")
        if r.get("ok"): r["deps"] = deps.mark_stale(project, stem)   # el keyframe cambió → shots STALE
        return r

    @app.post("/api/vid/upload")
    async def vid_upload(key: str = Form(...), file: UploadFile = File(...)):
        tmp = project.out / "shots_raw" / "_tmp"; tmp.mkdir(parents=True, exist_ok=True)
        dest = tmp / f"{key}.upload.{int(_t.time()*1000)}.mp4"; dest.write_bytes(await file.read())
        return editing.vid_accept(project, key, str(dest.relative_to(project.out)), note="reemplazo manual")

    @app.post("/api/anchor/upload")
    async def anchor_upload(id: str = Form(...), file: UploadFile = File(...)):
        dest = project.anchor_path(id); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            bak = project.out / "anchors" / "_versions"; bak.mkdir(parents=True, exist_ok=True)
            _sh.copy2(dest, bak / f"{id}.{int(_t.time()*1000)}.png")   # backup del anterior
        dest.write_bytes(await file.read())
        return {"ok": True, "id": id}

    # -------- post-producción: 4 pasos discretos (unify → vo → subs → master) --------
    from . import postprod

    def _bg(kind, label, fn):
        """Corre un paso en segundo plano (aparece en la cola global); guarda result/error en el job."""
        jid = _mk_job(kind, label, 1)
        def run():
            try:
                r = fn()
                with _LOCK:
                    _JOBS[jid]["result"] = r
                    if isinstance(r, dict) and r.get("error"): _JOBS[jid]["errors"].append(str(r["error"])[:180])
                    else: _JOBS[jid]["variants"].append(r)
            except Exception as ex:
                with _LOCK: _JOBS[jid]["errors"].append(f"{type(ex).__name__}: {str(ex)[:180]}")
            with _LOCK: _JOBS[jid]["done"] = True
        threading.Thread(target=run, daemon=True).start()
        return jid

    @app.get("/api/job/{jid}")
    def any_job(jid): return _JOBS.get(jid, {"error": "job desconocido"})

    @app.get("/api/post/state")
    def post_state(): return postprod.state(project)

    @app.post("/api/post/unify")            # PASO 1 (gratis, ffmpeg) — background
    def post_unify(): return {"job_id": _bg("post", "unificar", lambda: postprod.unify(project))}

    @app.post("/api/post/vo/prep")          # PASO 2 plan + costo estimado (NO gasta)
    def post_vo_prep(body: dict = Body(default={})): return postprod.vo_prep(project, body.get("lines"))

    @app.post("/api/post/vo/distribute")    # PASO 2 asistente: prosa → 1 línea por toma con IA
    def post_vo_distribute(body: dict = Body(...)): return postprod.vo_distribute(project, body.get("prose", ""))

    @app.post("/api/post/vo")               # PASO 2 (paga si LOOP_ALLOW_PAID) — background
    def post_vo(body: dict = Body(default={})):
        return {"job_id": _bg("post", "VO", lambda: postprod.vo_run(project, body.get("lines"), body.get("voice_id")))}

    @app.post("/api/post/subs")             # PASO 3 (gratis) — rápido, síncrono
    def post_subs(): return postprod.subs(project)

    @app.put("/api/post/subs")              # editar subtítulos a mano (nueva versión)
    def post_subs_edit(body: dict = Body(...)): return postprod.subs_edit(project, body.get("content", ""))

    @app.post("/api/post/master")           # PASO 4 (gratis) — gate + background
    def post_master(body: dict = Body(default={})):
        mm = postprod._load(project)
        st = {s: postprod._status(project, mm, s) for s in ("unify", "vo", "subs")}
        if any(v != "ready" for v in st.values()):
            bad = [s for s, v in st.items() if v != "ready"]
            return {"gated": True, "steps": st, "reason": f"rehacé primero: {', '.join(bad)} (deben estar 'listo', sin STALE)"}
        return {"job_id": _bg("post", "master", lambda: postprod.master(project, body.get("music")))}

    @app.post("/api/post/revert")
    def post_revert(body: dict = Body(...)): return postprod.revert(project, body["step"], body["v"])

    # -------- modo ACELERADO: batch keyframes → shots (Parte C) --------
    from . import batch

    @app.get("/api/batch/plan")
    def batch_plan(): return batch.plan(project)      # estimado, no gasta

    # -------- edición estructural del timeline (borrar/insertar keyframe) --------
    from . import timeline

    @app.post("/api/timeline/delete-keyframe")
    def tl_delete(body: dict = Body(...)): return timeline.delete_keyframe(project, body["stem"])

    @app.post("/api/timeline/insert-keyframe")
    def tl_insert(body: dict = Body(...)):
        return timeline.insert_keyframe(project, body["toma_n"], body.get("new_stem", ""),
                                        body.get("prompt", ""), body.get("refs"), body.get("dur_split"))

    @app.post("/api/timeline/add-toma")
    def tl_add_toma(body: dict = Body(...)):
        return timeline.add_toma(project, body.get("after", 0), body.get("duration", 6))

    @app.post("/api/batch/run")
    def batch_run():
        jid = _mk_job("batch", "keyframes+shots", 1)
        def prog(d):
            with _LOCK: _JOBS[jid]["progress"] = d
        def work():
            try:
                r = batch.run(project, progress=prog)
                with _LOCK:
                    _JOBS[jid]["result"] = r
                    if not r.get("dry"): _JOBS[jid]["variants"].append(r)
            except Exception as ex:
                with _LOCK: _JOBS[jid]["errors"].append(f"{type(ex).__name__}: {str(ex)[:180]}")
            with _LOCK: _JOBS[jid]["done"] = True
        threading.Thread(target=work, daemon=True).start()
        return {"job_id": jid}

    return app


def serve(project, port=8777, host="127.0.0.1"):
    import uvicorn
    from . import project as prj
    root = project.dir.parent
    active_file = root / ".active"                     # selección persistida entre reinicios
    if active_file.is_file():
        name = active_file.read_text().strip()
        if name and (root / name / "project.json").is_file():
            project = prj.load(root / name)
    ap = ActiveProject(project)                        # proxy: el front puede cambiar de proyecto sin reiniciar
    print(f"pipeline.server :: {'PAGA' if falx.paid_enabled() else 'DRY'} :: proyecto '{ap.name}' :: "
          f"http://{host}:{port}  (front en web/, apuntar VITE_API a esta URL)")
    uvicorn.run(build_app(ap), host=host, port=port, log_level="warning")
