"""Edición NO destructiva por plano (backend del front):
- KEYFRAME: Modo A (regen completa: prompt original + comentario + referencias) y Modo B (máscara + refs).
- VIDEO: regen de una toma con el mismo modelo + sus keyframes como guardrails.
Histórico durable de variantes (candidates), aceptar/revertir byte-exacto, persistencia de errores.
Toda llamada paga pasa por falx (candado de costo + timeout)."""
from __future__ import annotations
import json, base64, shutil, time, pathlib
from PIL import Image, ImageFilter
from . import falx, config


# ---------- helpers de metadatos ----------
def _load(p): return json.loads(p.read_text()) if p.is_file() else {}
def _save(p, m): p.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def _save_dataurl(project, data, tag):
    up = project.out / "_uploads"; up.mkdir(parents=True, exist_ok=True)
    dest = up / f"{tag}_{int(time.time()*1000)}.png"
    if isinstance(data, str) and data.startswith("data:"):
        dest.write_bytes(base64.b64decode(data.split(",", 1)[1]))
    else:
        Image.open(project.out / data if not str(data).startswith("/") else data).save(dest)
    return dest


def _resolve_refs(project, ref_images):
    out = []
    for i, r in enumerate(ref_images or []):
        if isinstance(r, str) and r.startswith("data:"):
            out.append(_save_dataurl(project, r, f"ref{i}"))
        else:
            p = project.resolve_ref(r) if not str(r).startswith(str(project.out)) else pathlib.Path(r)
            if p.is_file():
                out.append(p)
    return out


def _blend(base_path, edited_path, mask_path, dest):
    base = Image.open(base_path).convert("RGB")
    edited = Image.open(edited_path).convert("RGB").resize(base.size)
    mask = Image.open(mask_path).convert("L").resize(base.size).filter(ImageFilter.GaussianBlur(6))
    Image.composite(edited, base, mask).save(dest); return dest


# ================= KEYFRAMES =================
def kf_prep(project, stem, mode="A", comment="", instruction="", ref_images=None, hifi=False,
            strength=0.6, mask_png=None, num_variants=2, prompt=None, base_refs=None):
    meta = _load(project.kf_meta)
    if stem not in meta:
        return {"error": f"keyframe desconocido: {stem}"}
    e = meta[stem]; model = project.models["image_hifi"] if hifi or mode == "A" else project.models["image_hifi"]
    if mode == "A":
        base = prompt if (prompt is not None and prompt.strip()) else e["prompt"]  # prompt original editable desde el front
        prompt = base + ("\n\nADJUSTMENT (keep everything else the same): " + comment if comment else "")
        # refs del prompt: si el front manda base_refs, se usan EXACTAMENTE esas (control 100%);
        # si no, se usan las del keyframe (comportamiento previo).
        src_refs = base_refs if base_refs is not None else e.get("refs", [])
        anchors = [project.resolve_ref(r) for r in src_refs]
        anchors = [a for a in anchors if a.is_file()]
        refs = (_resolve_refs(project, ref_images) + anchors)[:14]
        return {"stem": stem, "mode": "A", "model": model, "prompt": prompt, "refs": refs,
                "est_cost_usd": config.est_image_cost(model, num_variants)}
    base = project.out / e["versions"][e["current"]]["path"]
    mask = _save_dataurl(project, mask_png, f"{stem}.mask") if mask_png else None
    refs = _resolve_refs(project, ref_images)
    return {"stem": stem, "mode": "B", "model": project.models["inpaint"], "base": base, "mask": mask,
            "ref0": refs[0] if refs else None, "strength": strength,
            "prompt": instruction or "seamlessly correct the masked region to match the rest of the scene",
            "est_cost_usd": config.est_image_cost(project.models["inpaint"], num_variants)}


def kf_regen_one(project, plan, idx):
    tmp = project.out / "keyframes" / "_tmp"; tmp.mkdir(parents=True, exist_ok=True)
    if plan["mode"] == "A":
        if plan["refs"]:
            url = falx.image_edit(plan["model"], plan["prompt"], plan["refs"], project.aspect, config.TIMEOUT_IMAGE)
        else:   # sin refs: el modelo /edit exige image_urls → caé a texto→imagen (como la etapa keyframes.run)
            url = falx.image_gen(plan["model"].replace("/edit", ""), plan["prompt"], project.aspect, config.TIMEOUT_IMAGE)
        dest = tmp / f"{plan['stem']}.A.{int(time.time()*1000)}.{idx}.png"; falx.download(url, dest)
    else:
        url = falx.inpaint(plan["model"], plan["prompt"], plan["base"], plan["mask"], plan["ref0"],
                           plan["strength"], None, config.TIMEOUT_IMAGE)
        raw = tmp / f"{plan['stem']}.B.raw.{int(time.time()*1000)}.{idx}.png"; falx.download(url, raw)
        dest = _blend(plan["base"], raw, plan["mask"], tmp / f"{plan['stem']}.B.{int(time.time()*1000)}.{idx}.png")
    rel = str(dest.relative_to(project.out))
    _kf_register(project, plan["stem"], rel, {"mode": plan["mode"], "model": plan["model"], "ts": None})
    return rel


def _kf_register(project, stem, rel, info):
    m = _load(project.kf_meta); e = m.get(stem)
    if not e:
        return
    c = e.setdefault("candidates", [])
    if not any(x["path"] == rel for x in c):
        c.append({"path": rel, **info}); _save(project.kf_meta, m)


def kf_variants(project, stem):
    m = _load(project.kf_meta); e = m.get(stem, {}); cands = list(e.get("candidates", []))
    known = {c["path"] for c in cands}; tmp = project.out / "keyframes" / "_tmp"
    for p in sorted(tmp.glob(f"{stem}.*.png")) if tmp.is_dir() else []:
        if ".mask." in p.name or ".raw." in p.name:
            continue
        rel = str(p.relative_to(project.out))
        if rel not in known:
            cands.append({"path": rel, "note": "recuperada", "ts": None})
    return [c for c in cands if (project.out / c["path"]).is_file()]


def kf_accept(project, stem, variant_path, note=""):
    m = _load(project.kf_meta); e = m.get(stem)
    if e is None:                       # keyframe NUEVO (p.ej. de una toma insertada): crear entrada mínima
        if stem not in project.keyframes:
            return {"error": f"keyframe '{stem}' no existe en el proyecto"}
        spec = project.keyframes.get(stem, {})
        e = {"stem": stem, "file": str(project.keyframe_path(stem).relative_to(project.out)),
             "prompt": spec.get("prompt", ""), "refs": spec.get("refs", []),
             "model": project.models["image_hifi"], "versions": [], "current": 0, "last_error": None}
        m[stem] = e
    vers = project.out / "keyframes" / "_versions"; vers.mkdir(parents=True, exist_ok=True)
    active = project.out / e["file"]
    v0 = next((x for x in e["versions"] if x["v"] == 0), None)
    if v0 and (project.out / v0["path"]).resolve() == active.resolve() and active.is_file():
        safe0 = vers / f"{stem}.v0.png"
        if not safe0.exists():
            shutil.copy2(active, safe0)
        v0["path"] = str(safe0.relative_to(project.out))
    n = max((x["v"] for x in e["versions"]), default=-1) + 1   # default -1 → primer accept de un kf nuevo = v0
    vp = vers / f"{stem}.v{n}.png"
    active.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project.out / variant_path, vp); shutil.copy2(vp, active)
    e["versions"].append({"v": n, "path": str(vp.relative_to(project.out)), "source": "edit", "note": note, "ts": None})
    e["current"] = n; e["last_error"] = None; _save(project.kf_meta, m)
    return {"ok": True, "current": n}


def kf_revert(project, stem, v):
    m = _load(project.kf_meta); e = m[stem]
    match = next((x for x in e["versions"] if x["v"] == v), None)
    if not match:
        return {"error": f"version {v} no existe"}
    shutil.copy2(project.out / match["path"], project.out / e["file"]); e["current"] = v; _save(project.kf_meta, m)
    return {"ok": True, "current": v}


def kf_set_error(project, stem, errs):
    m = _load(project.kf_meta)
    if stem in m:
        m[stem]["last_error"] = errs or None; _save(project.kf_meta, m)


# ================= VIDEO =================
def vid_prep(project, key, comment="", overrides=None, num_variants=2):
    m = _load(project.shots_meta); o = overrides or {}
    if key not in m:
        return {"error": f"toma desconocida: {key}"}
    e = m[key]; model = o.get("model") or e["model"]
    base = o.get("prompt") or e["prompt"]
    prompt = base + ("\n\nADJUSTMENT (keep the same start/end frames and overall look): " + comment if comment else "")
    start = project.out / (o.get("start_ref") or e["start_ref"]); end = project.out / (o.get("end_ref") or e["end_ref"])
    dur = o.get("duration") or e["params"]["duration"]; res = o.get("resolution") or e["params"]["resolution"]
    if not start.is_file() or not end.is_file():
        return {"error": f"faltan keyframes: {e['start_ref']} / {e['end_ref']}"}
    return {"key": key, "model": model, "prompt": prompt, "start": start, "end": end, "dur": dur, "res": res,
            "cfg": float(o.get("cfg_scale", 0.5)), "note": comment,
            "est_cost_usd": config.est_video_cost(model, res, dur, num_variants)}


def vid_regen_one(project, plan, idx):
    tmp = project.out / "shots_raw" / "_tmp"; tmp.mkdir(parents=True, exist_ok=True)
    url = falx.i2v(plan["model"], plan["prompt"], plan["start"], plan["end"], plan["dur"],
                   plan["res"], project.aspect, plan["cfg"], False, config.TIMEOUT_VIDEO)
    dest = tmp / f"{plan['key']}.{int(time.time()*1000)}.{idx}.mp4"; falx.download(url, dest)
    rel = str(dest.relative_to(project.out))
    _vid_register(project, plan["key"], rel, {"model": plan["model"], "duration": plan["dur"],
                                              "resolution": plan.get("res"), "note": plan.get("note", ""), "ts": None})
    return rel


def _vid_register(project, key, rel, info):
    m = _load(project.shots_meta); e = m.get(key)
    if not e:
        return
    c = e.setdefault("candidates", [])
    if not any(x["path"] == rel for x in c):
        c.append({"path": rel, **info}); _save(project.shots_meta, m)


def vid_variants(project, key):
    m = _load(project.shots_meta); e = m.get(key, {}); cands = list(e.get("candidates", []))
    known = {c["path"] for c in cands}; tmp = project.out / "shots_raw" / "_tmp"
    for p in sorted(tmp.glob(f"{key}.*.mp4")) if tmp.is_dir() else []:
        rel = str(p.relative_to(project.out))
        if rel not in known:
            cands.append({"path": rel, "model": e.get("model"), "note": "recuperada", "ts": None})
    return [c for c in cands if (project.out / c["path"]).is_file()]


def vid_accept(project, key, variant_path, note=""):
    m = _load(project.shots_meta); e = m[key]; active = project.shot_path(e["toma"])
    vers = project.out / "shots_raw" / "_versions"; vers.mkdir(parents=True, exist_ok=True)
    v0 = next((x for x in e["versions"] if x["v"] == 0), None)
    if v0 and (project.out / v0["path"]).resolve() == active.resolve() and active.is_file():
        safe0 = vers / f"{key}.v0.mp4"
        if not safe0.exists():
            shutil.copy2(active, safe0)
        v0["path"] = str(safe0.relative_to(project.out))
    n = max((x["v"] for x in e["versions"]), default=-1) + 1
    vp = vers / f"{key}.v{n}.mp4"; shutil.copy2(project.out / variant_path, vp); shutil.copy2(vp, active)
    e["versions"].append({"v": n, "path": str(vp.relative_to(project.out)), "source": "regen", "note": note, "ts": None})
    e["current"] = n; e["status"] = "approved"; e["last_error"] = None; _save(project.shots_meta, m)
    return {"ok": True, "current": n, "status": "approved"}


def vid_revert(project, key, v):
    m = _load(project.shots_meta); e = m[key]
    match = next((x for x in e["versions"] if x["v"] == v), None)
    if not match:
        return {"error": f"version {v} no existe"}
    shutil.copy2(project.out / match["path"], project.shot_path(e["toma"])); e["current"] = v; _save(project.shots_meta, m)
    return {"ok": True, "current": v}


def vid_set_status(project, key, status):
    m = _load(project.shots_meta); m[key]["status"] = status; _save(project.shots_meta, m)
    return {"ok": True, "status": status}


def vid_set_error(project, key, errs):
    m = _load(project.shots_meta)
    if key in m:
        m[key]["last_error"] = errs or None; _save(project.shots_meta, m)
