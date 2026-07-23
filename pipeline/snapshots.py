"""Snapshots de proyecto: respaldo COMPLETO (project.json + todo out/) en un .tar.gz, para poder
restaurar el estado EXACTO. Se guardan en projects/<name>/_snapshots/ — FUERA de out/, así ni los
resets ni los re-imports los tocan. Restaurar hace un auto-snapshot 'prerestore' antes, por seguridad."""
import tarfile, time, pathlib, shutil


def _dir(project):
    d = project.dir / "_snapshots"; d.mkdir(parents=True, exist_ok=True); return d


def save(project, label=""):
    d = _dir(project)
    label = "".join(c for c in (label or "") if c.isalnum() or c in "-_")[:40]
    name = f"{int(time.time())}" + (f"_{label}" if label else "")
    tar = d / f"{name}.tar.gz"
    pj = project.dir / "project.json"
    with tarfile.open(tar, "w:gz") as t:
        if pj.is_file():
            t.add(pj, arcname="project.json")
        if project.out.is_dir():
            t.add(project.out, arcname="out")   # _snapshots no está bajo out/ → sin recursión
    return {"ok": True, "snapshot": tar.name, "size_mb": round(tar.stat().st_size / 1e6, 2)}


def listing(project):
    d = _dir(project)
    return [{"name": f.name, "size_mb": round(f.stat().st_size / 1e6, 2), "ts": int(f.stat().st_mtime)}
            for f in sorted(d.glob("*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True)]


def restore(project, name):
    tar = _dir(project) / name
    if not tar.is_file():
        return {"error": f"snapshot '{name}' no existe"}
    save(project, label="prerestore")            # respaldo del estado actual ANTES de pisar
    if project.out.is_dir():
        shutil.rmtree(project.out)
    with tarfile.open(tar, "r:gz") as t:
        members = [m for m in t.getmembers() if m.name == "project.json" or m.name.startswith("out/") or m.name.startswith("out")]
        t.extractall(project.dir, members=members)
    return {"ok": True, "restored": name}
