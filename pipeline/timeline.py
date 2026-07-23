"""Edición ESTRUCTURAL del timeline: borrar / insertar keyframes, con su efecto en las tomas.

- BORRAR un keyframe que es frontera entre dos tomas consecutivas A(end==K) y B(start==K) las FUSIONA:
  la toma A pasa a ir de A.start → B.end (kf_n → kf_{n+2}) y B desaparece. El video de la toma fusionada
  queda para regenerar (su END cambió). Los keyframes del borde borrado se eliminan.
- INSERTAR un keyframe M dentro de una toma X la PARTE en dos: X = X.start→M y una nueva toma M→X.end.
  Ambas quedan para regenerar; el keyframe M nuevo hay que generarlo/subirlo.

Renumera las tomas 1..N y RE-MAPEA los crudos en disco (tomaNN.mp4) para que sigan alineados. Antes de
cada operación deja un snapshot de project.json (revertible). Reconstruye shots_meta desde los archivos."""
import json, time, shutil
from . import shots as shots_stage


def _save(project):
    (project.dir / "project.json").write_text(json.dumps(project.data, ensure_ascii=False, indent=2))

def _snapshot(project):
    snap = project.out / "_timeline_snapshots"; snap.mkdir(parents=True, exist_ok=True)
    dst = snap / f"project.{int(time.time()*1000)}.json"
    dst.write_text(json.dumps(project.data, ensure_ascii=False, indent=2))
    return str(dst.relative_to(project.out))

def _del_keyframe_files(project, stem):
    p = project.keyframe_path(stem)
    if p.is_file(): p.unlink()
    vers = project.out / "keyframes" / "_versions"
    if vers.is_dir():
        for f in vers.glob(f"{stem}.*"): f.unlink()
    project.data.get("keyframes", {}).pop(stem, None)
    if project.kf_meta.is_file():
        km = json.loads(project.kf_meta.read_text()); km.pop(stem, None)
        project.kf_meta.write_text(json.dumps(km, ensure_ascii=False, indent=2))

def _remap_and_finish(project, new_tomas, snap):
    """new_tomas: lista ordenada; cada toma trae old_n y _src (n de origen del crudo, o None si regenera).
    Renumera 1..N, mueve los mp4 al nuevo número, remapea content_blocked, guarda y reconstruye meta."""
    remap = {}                                   # old_n -> new_n (solo las que persisten con video)
    plan = []                                    # (new_n, src_old_n|None)
    for i, t in enumerate(new_tomas, 1):
        src = t.pop("_src", t.get("n"))
        remap[t["n"]] = i
        t["n"] = i
        plan.append((i, src))
    project.data["tomas"] = new_tomas
    # content_blocked_tomas → remapear a los nuevos números
    cb = project.data.get("content_blocked_tomas") or []
    project.data["content_blocked_tomas"] = sorted({remap[n] for n in cb if n in remap})

    raw = project.out / "shots_raw"; tmp = raw / "_remap"
    if tmp.is_dir(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    for new_n, src in plan:                      # copiar orígenes a tmp con el nuevo número
        if src is None: continue
        s = raw / f"toma{src:02d}.mp4"
        if s.is_file(): shutil.copy2(s, tmp / f"toma{new_n:02d}.mp4")
    for f in raw.glob("toma*.mp4"): f.unlink()   # limpiar los viejos
    for f in tmp.glob("*.mp4"): shutil.move(str(f), str(raw / f.name))
    shutil.rmtree(tmp)
    if project.shots_meta.is_file(): project.shots_meta.unlink()   # rebuild limpio (evita misattribution)
    _save(project)
    shots_stage.build_meta(project)
    return {"ok": True, "snapshot": snap, "tomas": len(new_tomas)}


def delete_keyframe(project, stem):
    if stem not in project.data.get("keyframes", {}):
        return {"error": f"keyframe '{stem}' no existe en el proyecto"}
    tomas = sorted(project.data["tomas"], key=lambda t: t["n"])
    as_end = [t for t in tomas if t["end"] == stem]
    as_start = [t for t in tomas if t["start"] == stem]
    if len(as_end) > 1 or len(as_start) > 1:
        return {"error": f"'{stem}' se usa en varios bordes; no forma una frontera simple"}
    snap = _snapshot(project)

    # Identificar el CORTE a colapsar: toma A (se extiende) y toma B (se absorbe y desaparece).
    A = B = None
    if as_end and as_start:                                    # frontera COMPARTIDA (mismo keyframe)
        A, B = as_end[0], as_start[0]
    elif as_end:                                               # K = END de A (frontera distinta o cierre)
        A = as_end[0]; B = next((t for t in tomas if t["n"] == A["n"] + 1), None)
    elif as_start:                                             # K = START de B (frontera distinta o apertura)
        B = as_start[0]; A = next((t for t in tomas if t["n"] == B["n"] - 1), None)

    orphans = {stem}                                           # keyframes a eliminar (K + su par del corte)
    if A and B:
        if B["n"] != A["n"] + 1:
            return {"error": f"'{stem}' no separa dos tomas consecutivas"}
        orphans.add(A["end"]); orphans.add(B["start"])         # ambos bordes del corte quedan sin uso
        A["end"] = B["end"]                                    # A ahora va A.start → B.end (kf_n → kf_{n+2})
        A["duration"] = int(A.get("duration", 5)) + int(B.get("duration", 5))
        A["_src"] = None                                       # la fusionada regenera (END nuevo)
        new_tomas = [t for t in tomas if t is not B]
        effect = f"fusionadas toma {A['n']} y {B['n']} → {A['start']} → {A['end']}; regenerá su video"
    elif B and not A:                                          # apertura: no hay toma previa → borra B
        new_tomas = [t for t in tomas if t is not B]
        effect = f"borrada la toma de apertura {B['n']}"
    elif A and not B:                                          # cierre: no hay toma siguiente → borra A
        new_tomas = [t for t in tomas if t is not A]
        effect = f"borrada la toma de cierre {A['n']}"
    else:
        return {"error": f"'{stem}' no está referenciado por ninguna toma"}

    # borrar solo los keyframes que ya no usa NINGUNA toma restante
    used = {t["start"] for t in new_tomas} | {t["end"] for t in new_tomas}
    for k in orphans:
        if k not in used:
            _del_keyframe_files(project, k)
    r = _remap_and_finish(project, new_tomas, snap)
    r["effect"] = effect; r["deleted_keyframes"] = sorted(orphans - used)
    return r


def add_toma(project, after, duration=6):
    """Inserta una toma NUEVA (con 2 keyframes nuevos vacíos) DESPUÉS de `after` tomas (0 = al inicio,
    N = al final). Hay que definir/generar esos 2 keyframes y el video. Renumera y re-mapea los crudos."""
    tomas = sorted(project.data["tomas"], key=lambda t: t["n"])
    after = int(after)
    if after < 0 or after > len(tomas):
        return {"error": f"posición inválida ({after}); rango 0..{len(tomas)}"}
    snap = _snapshot(project)
    tok = int(time.time() * 1000)
    start, end = f"ins{tok}_start", f"ins{tok}_end"
    project.data.setdefault("keyframes", {})[start] = {"prompt": "", "refs": []}
    project.data["keyframes"][end] = {"prompt": "", "refs": []}
    newt = {"n": after + 1, "code": f"ins{tok}", "title": "toma nueva", "start": start, "end": end,
            "duration": int(duration), "static": False, "motion": "", "vo": "", "_src": None}
    new_tomas = tomas[:after] + [newt] + tomas[after:]     # insertar en la posición
    r = _remap_and_finish(project, new_tomas, snap)
    r["effect"] = f"toma nueva insertada en posición {after + 1}; definí y generá sus 2 keyframes y su video"
    r["new_toma"] = after + 1
    r["new_keyframes"] = [start, end]
    return r


def insert_keyframe(project, toma_n, new_stem, prompt="", refs=None, dur_split=None):
    tomas = sorted(project.data["tomas"], key=lambda t: t["n"])
    X = next((t for t in tomas if t["n"] == int(toma_n)), None)
    if not X:
        return {"error": f"no existe la toma {toma_n}"}
    new_stem = (new_stem or "").strip()
    if not new_stem:
        return {"error": "falta el nombre del keyframe nuevo"}
    if new_stem in project.data.get("keyframes", {}):
        return {"error": f"el keyframe '{new_stem}' ya existe"}
    snap = _snapshot(project)

    project.data.setdefault("keyframes", {})[new_stem] = {"prompt": prompt or "", "refs": refs or []}
    dtot = int(X.get("duration", 6))
    d1 = int(dur_split) if dur_split else max(1, dtot // 2)
    d2 = max(1, dtot - d1)
    newB = {"n": X["n"] + 1, "code": (X.get("code", "") + "_split"), "title": (X.get("title", "") + " (b)"),
            "start": new_stem, "end": X["end"], "duration": d2, "static": False,
            "motion": X.get("motion", ""), "vo": "", "_src": None}     # nueva → sin video
    X["end"] = new_stem; X["duration"] = d1; X["_src"] = None          # X regenera (END nuevo)
    new_tomas = []
    for t in tomas:
        new_tomas.append(t)
        if t is X: new_tomas.append(newB)
    r = _remap_and_finish(project, new_tomas, snap)
    r["effect"] = (f"toma {toma_n} dividida en 2 insertando '{new_stem}'; generá ese keyframe y regenerá "
                   f"ambas tomas")
    return r
