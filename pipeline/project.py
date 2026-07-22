"""Abstracción de PROYECTO: hace el pipeline reusable para cualquier concepto/video.

Un proyecto es una carpeta `projects/<nombre>/` con:
  - project.json  : personajes/sets (anchors), keyframes (prompts+refs), tomas (motion/duración/vo), voz, modelos
  - biblia.md     : guion/biblia (referencia humana; opcional)
  - captures/     : imágenes de referencia crudas (livianas en el ejemplo; reales fuera del repo)
Las salidas generadas van a `projects/<nombre>/out/` (gitignored). Nada de esto está hardcodeado al pipeline.
"""
from __future__ import annotations
import json, pathlib
from . import config


class Project:
    def __init__(self, path):
        self.dir = pathlib.Path(path).resolve()
        cfgfile = self.dir / "project.json"
        if not cfgfile.is_file():
            raise FileNotFoundError(f"No existe {cfgfile}. Pasá --project projects/<nombre>.")
        self.data = json.loads(cfgfile.read_text())
        self.out = self.dir / "out"
        for sub in ("anchors", "keyframes/shots", "keyframes/seams", "shots_raw",
                    "vo", "_tmp", "_versions"):
            (self.out / sub).mkdir(parents=True, exist_ok=True)

    # --- propiedades de config ---
    @property
    def name(self): return self.data.get("name", self.dir.name)
    @property
    def style(self): return self.data.get("style", "")
    @property
    def aspect(self): return self.data.get("aspect_ratio", "16:9")
    @property
    def voice_id(self): return self.data.get("voice_id", config.DEFAULT_VOICE_ID)
    @property
    def models(self): return config.models(self.data)
    @property
    def anchors(self): return self.data.get("anchors", {})           # {id: {prompt, refs}}
    @property
    def keyframes(self): return self.data.get("keyframes", {})       # {stem: {prompt, refs}}
    @property
    def tomas(self): return self.data.get("tomas", [])               # [{n,title,motion,duration,static,vo,start,end}]
    @property
    def content_blocked(self): return set(self.data.get("content_blocked_tomas", []))

    # --- resolución de rutas ---
    def resolve_ref(self, ref: str) -> pathlib.Path:
        """Un ref puede ser: id de anchor (→ out/anchors/<id>.png), ruta 'captures/...' o ruta literal."""
        if ref in self.anchors:
            return self.out / "anchors" / f"{ref}.png"
        p = self.dir / ref
        if p.is_file() or ref.startswith("captures/"):
            return p
        return pathlib.Path(ref)

    def anchor_path(self, anchor_id): return self.out / "anchors" / f"{anchor_id}.png"

    def keyframe_path(self, stem):
        sub = "seams" if stem.startswith("seam") else "shots"
        return self.out / "keyframes" / sub / f"{stem}.png"

    def shot_path(self, n): return self.out / "shots_raw" / f"toma{int(n):02d}.mp4"
    def vo_path(self, i): return self.out / "vo" / f"line_{i}.mp3"
    @property
    def kf_meta(self): return self.out / "keyframes" / "keyframes_meta.json"
    @property
    def shots_meta(self): return self.out / "shots_raw" / "shots_meta.json"
    @property
    def master_raw(self): return self.out / "master_raw.mp4"
    @property
    def master(self): return self.out / "master.mp4"

    # --- plan de dependencias (seams compartidos) derivado de las tomas ---
    def seam_plan(self):
        """Devuelve (shots, boundaries). Un seam compartido = end_ref[N] == start_ref[N+1]."""
        tomas = sorted(self.tomas, key=lambda t: t["n"])
        shots = {t["n"]: {"n": t["n"], "start": t["start"], "end": t["end"]} for t in tomas}
        boundaries = []
        for a, b in zip(tomas, tomas[1:]):
            shared = a["end"] == b["start"]
            boundaries.append({"from": a["n"], "to": b["n"],
                               "type": "shared" if shared else "distinct",
                               "seam": a["end"] if shared else None})
        return shots, boundaries

    def unique_keyframes(self):
        """Stems únicos a generar (los seams compartidos aparecen una sola vez)."""
        seen, order = set(), []
        for t in sorted(self.tomas, key=lambda t: t["n"]):
            for stem in (t["start"], t["end"]):
                if stem not in seen:
                    seen.add(stem); order.append(stem)
        return order


def load(path) -> Project:
    return Project(path)
