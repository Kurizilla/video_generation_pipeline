"""API del pipeline (FastAPI) — backend del front React. Opera todas las etapas de UN proyecto:
navegar anchors/keyframes/tomas, disparar generaciones por etapa, editor de keyframes (A/B), regen de
video por plano, grafo keyframe→video con STALE, y el GO final (assemble). Guarda la FAL_KEY en el backend
(el navegador nunca la ve). Regen de imagen/video ASÍNCRONA (job + polling). Sin LOOP_ALLOW_PAID=1 → dry.
"""
import json, threading, uuid
from . import deps, editing, anchors, keyframes, shots, assemble, falx

_JOBS = {}; _LOCK = threading.Lock()


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
    for i in range(n):
        try:
            with _LOCK: _JOBS[jid]["variants"].append(fn(plan, i))
        except Exception as ex:
            with _LOCK: _JOBS[jid]["errors"].append(f"{type(ex).__name__}: {str(ex)[:180]}")
    with _LOCK: _JOBS[jid]["done"] = True
    return _JOBS[jid]["errors"]


def build_app(project):
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

    @app.get("/api/tomas")
    def tomas(): return _view_tomas(project)

    @app.get("/api/kf/{stem}")
    def kf_meta(stem): return editing._load(project.kf_meta).get(stem, {"error": "no existe"})

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
                               body.get("strength", 0.6), body.get("mask_png"), n)
        if "error" in plan: return plan
        if not falx.paid_enabled(): return {"dry": True, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}
        jid = uuid.uuid4().hex[:12]; _JOBS[jid] = {"variants": [], "errors": [], "done": False, "total": n, "kind": "kf", "stem": body["stem"]}
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
        jid = uuid.uuid4().hex[:12]; _JOBS[jid] = {"variants": [], "errors": [], "done": False, "total": n, "kind": "vid", "key": body["key"]}
        threading.Thread(target=lambda: (_worker(jid, lambda pl, i: editing.vid_regen_one(project, pl, i), plan, n),
                                         editing.vid_set_error(project, body["key"], _JOBS[jid]["errors"])), daemon=True).start()
        return {"job_id": jid, "total": n, "model": plan["model"], "est_cost_usd": plan["est_cost_usd"]}

    @app.get("/api/vid/status/{jid}")
    def vid_status_job(jid): return _JOBS.get(jid, {"error": "job desconocido"})
    @app.get("/api/vid/variants/{key}")
    def vid_vars(key): return {"variants": editing.vid_variants(project, key)}
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

    return app


def serve(project, port=8777, host="127.0.0.1"):
    import uvicorn
    print(f"pipeline.server :: {'PAGA' if falx.paid_enabled() else 'DRY'} :: proyecto '{project.name}' :: "
          f"http://{host}:{port}  (front en web/, apuntar VITE_API a esta URL)")
    uvicorn.run(build_app(project), host=host, port=port, log_level="warning")
