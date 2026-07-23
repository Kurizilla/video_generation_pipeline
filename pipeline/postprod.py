"""Post-producción DESACOPLADA en 4 pasos discretos, reintentables y versionados:
  1) unify  : concat de los shots aprobados -> unified_vN.mp4 + timeline de cortes
  2) vo      : una línea de VO por toma (ElevenLabs), timeada a las tomas (como siempre); script editable
  3) subs    : subtítulos verbatim desde las líneas + timings -> subs_vN.srt (editable)
  4) master  : mux unified + VO + subs (+música) -> master_vN.mp4   [gate: 1-3 listos y sin STALE]

Cada paso guarda EN SU VERSIÓN la firma de sus insumos (dep_sig). Si un insumo aguas arriba cambia
(regenerás un shot -> cae unify; re-unificás -> cae vo; nueva vo -> caen subs y master), el paso queda
STALE y el front avisa qué rehacer. Nada se pierde: cada paso versiona y es revertible.

NO-SPEND: la VO respeta el candado de costo (dry = plan + costo estimado, sin sintetizar). Sin LLM.
Reusa los helpers ffmpeg de `assemble` (concat, ffprobe, mux de audio)."""
import json, time, subprocess, shutil, pathlib
from . import falx, tts, editing, assemble

POST = "post"                       # subcarpeta de artefactos versionados: project.out/post/
MANIFEST = "postprod.json"
VO_GAP = 0.12                       # silencio mínimo entre líneas de VO (s) — evita que se pisen, sin pausas largas
VO_DRIFT_WARN = 0.5                 # aviso QA: línea que quedó > este corrimiento respecto a su toma (s)


# ---------------- estado / versionado ----------------
def _dir(project):
    d = project.out / POST; d.mkdir(parents=True, exist_ok=True); return d

def _load(project):
    f = project.out / MANIFEST
    return json.loads(f.read_text()) if f.is_file() else {}

def _save(project, m):
    (project.out / MANIFEST).write_text(json.dumps(m, ensure_ascii=False, indent=2))

def _next_v(m, step):
    return max([x["v"] for x in m.get(step, {}).get("versions", [])], default=-1) + 1

def _cur(m, step):
    e = m.get(step, {})
    return e.get("current", -1) if e.get("versions") else -1

def _cur_entry(m, step):
    e = m.get(step)
    if not e or not e.get("versions"): return None
    cur = e.get("current", e["versions"][-1]["v"])
    return next(({**x} for x in e["versions"] if x["v"] == cur), None)

def _register(project, m, step, ver_obj, dep_sig):
    v = _next_v(m, step)
    ver_obj = {"v": v, "ts": time.time(), "dep_sig": dep_sig, **ver_obj}
    e = m.setdefault(step, {})
    e.setdefault("versions", []).append(ver_obj)
    e["current"] = v
    return v


# ---------------- firmas de dependencia (STALE) ----------------
def _tkey(n): return f"toma{int(n):02d}"

def _shots_sig(project):
    """Firma de los shots aprobados: si cambia versión/estado de alguna toma, unify queda STALE."""
    sm = editing._load(project.shots_meta)
    parts = []
    for t in sorted(project.tomas, key=lambda x: x["n"]):
        e = sm.get(_tkey(t["n"]), {})
        parts.append(f"{t['n']}:{e.get('current', 0)}:{e.get('status', 'pending')}")
    return "|".join(parts)

def _dep_sig_live(project, m, step):
    if step == "unify": return _shots_sig(project)
    if step == "vo":    return f"unify:{_cur(m, 'unify')}"
    if step == "subs":  return f"vo:{_cur(m, 'vo')}"
    if step == "master":return f"unify:{_cur(m,'unify')}|vo:{_cur(m,'vo')}|subs:{_cur(m,'subs')}"
    return ""

def _status(project, m, step):
    cur = _cur_entry(m, step)
    if not cur: return "pending"
    return "ready" if cur.get("dep_sig") == _dep_sig_live(project, m, step) else "stale"


# ---------------- líneas de VO por toma ----------------
def _lines(project, override=None):
    """Líneas de VO en orden de toma. override: {n(int): texto} para editar el script sin tocar project.json."""
    out = []
    for i, t in enumerate(sorted(project.tomas, key=lambda x: x["n"])):
        txt = t.get("vo", "")
        if isinstance(override, dict):
            txt = override.get(str(t["n"]), override.get(t["n"], txt))
        out.append({"n": t["n"], "idx": i, "text": (txt or "").strip()})
    return out

def _line_cached(project, idx, text):
    wp = project.vo_path(idx); hp = project.out / "vo" / f"line_{idx}.txt"
    if not (wp.is_file() and wp.stat().st_size > 2000): return False
    return (not hp.is_file()) or hp.read_text() == text   # sin sidecar => cache legacy (se asume vigente)


# ================= PASO 1 — UNIFICAR =================
def unify(project):
    tomas = sorted(project.tomas, key=lambda t: t["n"])
    paths = [project.shot_path(t["n"]) for t in tomas]
    missing = [p.name for p in paths if not p.is_file()]
    if missing: return {"error": f"faltan shots: {missing}"}
    m = _load(project); d = _dir(project); v = _next_v(m, "unify")
    dest = d / f"unified.v{v}.mp4"
    lst = project.out / "_concat.txt"; lst.write_text("".join(f"file '{p}'\n" for p in paths))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24",
           "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
           str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True); lst.unlink(missing_ok=True)
    if r.returncode != 0: return {"error": r.stderr[-800:]}
    cuts = []; acc = 0.0
    for t, p in zip(tomas, paths):
        du = assemble._dur(p)
        cuts.append({"toma": t["n"], "t0": round(acc, 3), "t1": round(acc + du, 3), "dur": round(du, 3)}); acc += du
    _register(project, m, "unify",
              {"path": f"{POST}/unified.v{v}.mp4", "dur": round(acc, 3), "cuts": cuts}, _shots_sig(project))
    _save(project, m)
    return {"ok": True, "v": v, "duration": round(acc, 3), "cuts": cuts}


# ================= PASO 2 — VO =================
def vo_prep(project, lines=None):
    """Plan + costo estimado, SIN sintetizar (para el gate NO-SPEND)."""
    m = _load(project); u = _cur_entry(m, "unify")
    if not u: return {"error": "primero unificá (paso 1): la VO se timea al video unificado"}
    cuts = {c["toma"]: c for c in u["cuts"]}
    plan = []
    for it in _lines(project, lines):
        c = cuts.get(it["n"], {})
        plan.append({"n": it["n"], "idx": it["idx"], "text": it["text"], "chars": len(it["text"]),
                     "t0": c.get("t0"), "dur": c.get("dur"), "skip": not it["text"],
                     "cached": _line_cached(project, it["idx"], it["text"])})
    to_synth = [p for p in plan if not p["cached"] and not p["skip"]]
    chars = sum(p["chars"] for p in to_synth)
    est = round(chars / 1000 * 0.30, 3)   # estimación ~ElevenLabs (VERIFICAR en elevenlabs.io/pricing)
    return {"plan": plan, "to_synth": len(to_synth), "chars": chars, "est_cost_usd": est,
            "voice_id": project.voice_id, "paid": falx.paid_enabled()}

def _vo_qa(script, video_dur):
    """QA de cómo quedaron los audios: solapamiento (garantizado 0 por el scheduling), corrimiento de
    cada línea respecto a su toma, y si la VO se pasa del largo del video (se cortaría por -shortest)."""
    drifted = [{"n": s["n"], "drift": s["drift"]} for s in script if s["drift"] > VO_DRIFT_WARN]
    # línea cuya locución sigue sonando cuando visualmente ya empezó la toma siguiente (informativo)
    lag = []
    for a, b in zip(script, script[1:]):
        over = (a["start"] + a["audio_dur"]) - b["toma_start"]
        if over > 0.03:
            lag.append({"n": a["n"], "sigue_en": b["n"], "ms": int(round(over * 1000))})
    tail = round(script[-1]["start"] + script[-1]["audio_dur"], 3) if script else 0.0
    return {"overlap_free": True,                         # el scheduling impide que dos pistas se pisen
            "lines": len(script),
            "max_drift": round(max((s["drift"] for s in script), default=0.0), 3),
            "drifted_lines": drifted,                     # quedaron corridas (acortá su texto para recuperar sync)
            "lagging_lines": lag,                         # narración que cruza el corte visual (normal, informativo)
            "vo_end": tail, "video_dur": round(video_dur, 3),
            "tail_overflow": round(max(0.0, tail - video_dur), 3)}   # >0 => la VO se pasa del video


def vo_qa(project):
    """Devuelve el QA de la versión de VO actual (para el front)."""
    vo = _cur_entry(_load(project), "vo")
    return vo.get("qa") if vo else {"error": "no hay VO generada"}


def vo_distribute(project, prose):
    """IA: reparte/adapta un guion en PROSA entre las tomas (1 línea por toma), ajustando a la duración
    de cada toma. La IA recibe título/acción/duración/línea-actual de cada toma. Solo texto, sin marcas.
    Devuelve {n(str): texto} para poblar las casillas del front (el usuario revisa antes de sintetizar)."""
    import re
    from . import llm
    if not (prose or "").strip():
        return {"error": "pegá un guion en prosa primero"}
    if not llm.available():
        return {"error": "Sin credencial LLM: logueate con gcloud (Vertex/Gemini) o poné ANTHROPIC_API_KEY/OPENAI_API_KEY (ver .env.example)."}
    if not falx.paid_enabled():
        return {"error": "Distribuir con IA usa un LLM (pago). Poné el server en PAGA (LOOP_ALLOW_PAID=1)."}
    m = _load(project); u = _cur_entry(m, "unify")
    dur_by_n = {c["toma"]: c["dur"] for c in u["cuts"]} if u else {}
    rows = []
    for t in sorted(project.tomas, key=lambda x: x["n"]):
        d = dur_by_n.get(t["n"])
        if d is None:
            sp = project.shot_path(t["n"]); d = assemble._dur(sp) if sp.is_file() else float(t.get("duration") or 5)
        rows.append({"n": t["n"], "title": t.get("title", ""), "motion": t.get("motion", ""),
                     "dur": round(float(d), 2), "current": t.get("vo", "")})
    system = ("Sos editor de voz en off para un corto animado. Distribuís el GUION EN PROSA que te da el "
              "usuario entre las tomas, UNA línea por toma, adaptando/parafraseando ese texto para que quepa "
              "hablado en la duración de cada toma (ritmo ~2.5 palabras/seg). El contenido de cada línea debe "
              "salir EXCLUSIVAMENTE de la prosa dada — NO reuses ni copies ningún guion anterior; si la prosa "
              "cambia, la salida debe cambiar. Usá el título y la acción de cada toma solo para decidir qué "
              "parte de la prosa va en cuál y respetar el orden narrativo. Texto plano locutable, SIN marcas, "
              "acotaciones ni tonos. Devolvé SOLO JSON: {\"lines\": {\"<n>\": \"<texto>\"}}, una entrada por toma.")
    lst = "\n".join(f'{r["n"]}) {r["dur"]}s · máx≈{int(r["dur"]*2.5)} palabras · {r["title"]} · '
                    f'acción: {r["motion"][:120]}' for r in rows)   # sin "actual": no anclar en el guion previo
    user = (f"GUION EN PROSA A DISTRIBUIR (única fuente del texto):\n{prose.strip()}\n\n"
            f"TOMAS (dónde repartirlo):\n{lst}\n\nDevolvé el JSON con una línea por toma, basada solo en la prosa.")
    try:
        txt = llm.complete(system, user, max_tokens=8192)   # holgado: modelos "thinking" gastan tokens de salida
    except Exception as e:
        return {"error": f"LLM: {type(e).__name__}: {str(e)[:160]}"}
    clean = re.sub(r"^```(?:json)?|```$", "", (txt or "").strip(), flags=re.M).strip()   # quita fences ```json
    mo = re.search(r"\{.*\}", clean, re.S)
    if not mo:
        return {"error": "el LLM no devolvió JSON (¿respuesta truncada?)", "raw": txt[:400]}
    try:
        data = json.loads(mo.group(0))
    except Exception:
        return {"error": "JSON inválido del LLM", "raw": txt[:400]}
    src = data.get("lines", data)
    lines = {str(k): (v or "").strip() for k, v in src.items()}
    return {"ok": True, "lines": lines}


def vo_run(project, lines=None, voice_id=None):
    """Sintetiza (si falta) una línea por toma y SNAPSHOTEA una versión. Respeta el candado de costo."""
    m = _load(project); u = _cur_entry(m, "unify")
    if not u: return {"error": "primero unificá (paso 1)"}
    ls = _lines(project, lines); vid = voice_id or project.voice_id
    cuts = {c["toma"]: c for c in u["cuts"]}
    dry = not falx.paid_enabled()
    work = project.out / "vo"; work.mkdir(parents=True, exist_ok=True)
    need_paid = 0
    for it in ls:
        if not it["text"]: continue
        if not _line_cached(project, it["idx"], it["text"]):
            if dry: need_paid += 1; continue
            try:
                tts.synth(it["text"], project.vo_path(it["idx"]), vid)
                (work / f"line_{it['idx']}.txt").write_text(it["text"])
            except Exception as ex:
                return {"error": f"toma{it['n']}: {type(ex).__name__}: {str(ex)[:150]}"}
    if dry and need_paid:
        return {"dry": True, **vo_prep(project, lines)}    # no snapshotea: mostrá el estimado y esperá PAGA
    # snapshot de la versión
    d = _dir(project); v = _next_v(m, "vo"); vdir = d / f"vo.v{v}"; vdir.mkdir(parents=True, exist_ok=True)
    # SCHEDULING sin solapamiento: cada línea arranca en su toma, pero NUNCA antes de que termine la
    # anterior (+ VO_GAP). Garantiza fluidez (dos voces nunca se pisan) sin pausas largas. Los subs y el
    # master leen este 'start' ya agendado, así que quedan en sync con el audio real.
    script = []; prev_end = 0.0
    for it in ls:
        if not it["text"]: continue
        src = project.vo_path(it["idx"]); seg_dur = 0.0
        if src.is_file():
            shutil.copy2(src, vdir / f"line_{it['idx']}.mp3"); seg_dur = assemble._dur(src)
        c = cuts.get(it["n"], {}); toma_start = float(c.get("t0") or 0.0)
        start = max(toma_start, prev_end + (VO_GAP if prev_end > 0 else 0.0))
        prev_end = start + seg_dur
        script.append({"n": it["n"], "idx": it["idx"], "text": it["text"],
                       "toma_start": round(toma_start, 3), "start": round(start, 3),
                       "toma_dur": c.get("dur"), "audio_dur": round(seg_dur, 3),
                       "drift": round(start - toma_start, 3)})
    qa = _vo_qa(script, u["dur"])
    (d / f"vo_script.v{v}.json").write_text(json.dumps(script, ensure_ascii=False, indent=2))
    _register(project, m, "vo",
              {"dir": f"{POST}/vo.v{v}", "script": f"{POST}/vo_script.v{v}.json", "voice_id": vid,
               "lines": [x["text"] for x in ls], "qa": qa}, f"unify:{_cur(m, 'unify')}")
    _save(project, m)
    return {"ok": True, "v": v, "voice_id": vid, "script": script, "qa": qa}


# ================= PASO 3 — SUBTÍTULOS =================
def _ts(sec):
    sec = max(0.0, float(sec or 0)); h = int(sec // 3600); mnt = int((sec % 3600) // 60)
    s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{mnt:02d}:{s:02d},{ms:03d}"

def subs(project):
    """SRT verbatim desde el script temporizado de la VO (paso 2)."""
    m = _load(project); vo = _cur_entry(m, "vo")
    if not vo: return {"error": "primero generá la VO (paso 2): los subtítulos salen de su script temporizado"}
    script = json.loads((project.out / vo["script"]).read_text())
    blocks = []
    for i, seg in enumerate(script, 1):
        start = seg.get("start") or 0
        dur = max(seg.get("audio_dur") or 0, min(seg.get("toma_dur") or 2.0, 2.0))
        blocks.append(f"{i}\n{_ts(start)} --> {_ts(start + dur)}\n{seg['text']}\n")
    d = _dir(project); v = _next_v(m, "subs"); dest = d / f"subs.v{v}.srt"
    dest.write_text("\n".join(blocks))
    _register(project, m, "subs", {"path": f"{POST}/subs.v{v}.srt"}, f"vo:{_cur(m, 'vo')}")
    _save(project, m)
    return {"ok": True, "v": v, "srt": dest.read_text()}

def _srt2s(t):
    t = t.strip().replace(",", "."); h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def _parse_srt(text):
    """SRT -> [{start, end, text}] (para quemar como overlays; respeta ediciones a mano)."""
    segs = []
    for block in (text or "").strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        tl = next((l for l in lines if "-->" in l), None)
        if not tl: continue
        a, b = tl.split("-->")
        txt = " ".join(lines[lines.index(tl) + 1:])
        if txt: segs.append({"start": _srt2s(a), "end": _srt2s(b), "text": txt})
    return segs

def subs_edit(project, content):
    """Guarda subtítulos editados a mano como NUEVA versión (revertible), con la misma dep_sig actual."""
    m = _load(project)
    if not _cur_entry(m, "subs"): return {"error": "no hay subtítulos que editar (generalos primero)"}
    d = _dir(project); v = _next_v(m, "subs"); dest = d / f"subs.v{v}.srt"
    dest.write_text(content or "")
    _register(project, m, "subs", {"path": f"{POST}/subs.v{v}.srt", "edited": True}, f"vo:{_cur(m, 'vo')}")
    _save(project, m)
    return {"ok": True, "v": v}


# ================= PASO 4 — MASTER =================
def master(project, music=None):
    m = _load(project)
    st = {s: _status(project, m, s) for s in ("unify", "vo", "subs")}
    if any(v != "ready" for v in st.values()):
        bad = [s for s, v in st.items() if v != "ready"]
        return {"gated": True, "steps": st, "reason": f"rehacé primero: {', '.join(bad)} (deben estar 'listo', sin STALE)"}
    u = _cur_entry(m, "unify"); vo = _cur_entry(m, "vo"); sub = _cur_entry(m, "subs")
    video = project.out / u["path"]; vdir = project.out / vo["dir"]; srt = project.out / sub["path"]
    VID = u["dur"]
    script = json.loads((project.out / vo["script"]).read_text())
    inp = ["-i", str(video)]; idx = 1; vo_map = []
    for seg in script:
        p = vdir / f"line_{seg['idx']}.mp3"
        if p.is_file(): inp += ["-i", str(p)]; vo_map.append((idx, seg)); idx += 1
    # subtítulos: PNG overlays por bloque del SRT (este ffmpeg no trae libass) — respeta ediciones a mano
    sub_segs = _parse_srt(srt.read_text())
    sub_in = []
    for i, sg in enumerate(sub_segs):
        png = assemble._render_sub(project, f"post_{i}", sg["text"])
        if png: inp += ["-loop", "1", "-i", str(png)]; sub_in.append((idx, sg)); idx += 1
    music_idx = None
    music = music or project.data.get("music")
    if music and pathlib.Path(music).is_file(): inp += ["-stream_loop", "-1", "-i", str(music)]; music_idx = idx; idx += 1
    fg = ""; prev = "0:v"
    for k, (sidx, sg) in enumerate(sub_in):
        fg += f"[{prev}][{sidx}:v]overlay=0:0:enable='between(t,{sg['start']:.2f},{sg['end']:.2f})'[s{k}];"; prev = f"s{k}"
    fg += f"[{prev}]format=yuv420p[vout];"
    va = []
    for vidx, seg in vo_map:
        ms = int((seg.get("start") or 0) * 1000); fg += f"[{vidx}:a]adelay={ms}|{ms}[va{vidx}];"; va.append(f"[va{vidx}]")
    aout = None
    if va:
        fg += "".join(va) + f"amix=inputs={len(va)}:normalize=0[voice];[voice]apad=whole_dur={VID:.3f}[voicep];"
        aout = "[voicep]"
        if music_idx is not None:
            fg += f"[{music_idx}:a]volume=0.12,atrim=0:{VID:.3f}[mus];[voicep][mus]amix=inputs=2:duration=first:normalize=0[aout];"
            aout = "[aout]"
    d = _dir(project); v = _next_v(m, "master"); dest = d / f"master.v{v}.mp4"
    cmd = ["ffmpeg", "-y"] + inp + ["-filter_complex", fg.rstrip(";"), "-map", "[vout]"] + \
          (["-map", aout] if aout else []) + \
          ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24"] + \
          (["-c:a", "aac", "-b:a", "192k", "-shortest"] if aout else []) + [str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: return {"error": r.stderr[-900:]}
    shutil.copy2(dest, project.master)      # master.mp4 canónico apunta a la última versión
    _register(project, m, "master", {"path": f"{POST}/master.v{v}.mp4"},
              f"unify:{u['v']}|vo:{vo['v']}|subs:{sub['v']}")
    _save(project, m)
    return {"ok": True, "v": v, "duration": assemble._dur(dest)}


# ================= estado + revert (para el front) =================
def state(project):
    m = _load(project); out = {}
    for s in ("unify", "vo", "subs", "master"):
        e = m.get(s, {})
        out[s] = {"status": _status(project, m, s), "current": e.get("current", -1),
                  "versions": e.get("versions", []), "artifact": _cur_entry(m, s)}
    out["master"]["can_build"] = all(_status(project, m, x) == "ready" for x in ("unify", "vo", "subs"))
    return out

def revert(project, step, v):
    m = _load(project); e = m.get(step)
    if not e or not any(x["v"] == v for x in e.get("versions", [])): return {"error": f"{step}: no existe v{v}"}
    e["current"] = v; _save(project, m)
    return {"ok": True, "step": step, "current": v}
