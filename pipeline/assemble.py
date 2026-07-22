"""Etapa 5 (unificación / [GO]): concat de shots aprobados → master_raw; VO (ElevenLabs) por toma;
subtítulos verbatim quemados; música opcional duckeada → master.mp4.
GATE: solo procede si no hay STALE y todas las tomas están aprobadas. Dry-run sin gasto para la VO."""
from __future__ import annotations
import json, subprocess, pathlib
from . import falx, config, tts, deps

FONT_CANDIDATES = ["/Library/Fonts/Arial Unicode.ttf",
                   "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout or 0)


def _font():
    from PIL import ImageFont
    for f in FONT_CANDIDATES:
        if pathlib.Path(f).is_file():
            return f
    return None


def build_master_raw(project):
    """Concat de los crudos aprobados (cortes duros → respeta seams) → master_raw.mp4."""
    tomas = sorted(project.tomas, key=lambda t: t["n"])
    paths = [project.shot_path(t["n"]) for t in tomas]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        return {"error": f"faltan crudos: {missing}"}
    lst = project.out / "_concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in paths))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24",
           "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
           str(project.master_raw)]
    r = subprocess.run(cmd, capture_output=True, text=True); lst.unlink(missing_ok=True)
    if r.returncode != 0:
        return {"error": r.stderr[-800:]}
    return {"ok": True, "duration": _dur(project.master_raw)}


def synth_vo(project):
    """Sintetiza una línea de VO por toma (project.tomas[*].vo). Dry-run imprime el plan."""
    dry = not falx.paid_enabled()
    tomas = sorted(project.tomas, key=lambda t: t["n"])
    print(f"== VO :: {'DRY (no gasta)' if dry else 'PAGA'} :: voz {project.voice_id} :: {len(tomas)} líneas ==")
    for i, t in enumerate(tomas):
        line = t.get("vo", "").strip()
        dest = project.vo_path(i)
        if not line:
            print(f"  [skip] toma{t['n']:02d} sin línea de VO"); continue
        if dest.is_file() and dest.stat().st_size > 2000:
            print(f"  [cache] line_{i}"); continue
        if dry:
            print(f"  [DRY]  line_{i}: “{line[:60]}…”"); continue
        try:
            r = tts.synth(line, dest, project.voice_id)
            print(f"  [OK]   line_{i} ({r['model']})")
        except Exception as e:
            print(f"  [FAIL] line_{i} {type(e).__name__}: {str(e)[:120]}")


def _render_sub(project, i, txt, W=1920, H=1080):
    from PIL import Image, ImageDraw, ImageFont
    font = _font()
    if not font:
        return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = ImageFont.truetype(font, 42)
    lines, cur = [], ""
    for w in txt.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= 1480:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    y0 = H - 110 - 54 * len(lines)
    for j, ln in enumerate(lines):
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y0 + 54 * j), ln, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(18, 22, 28, 235))
    dst = project.out / "_tmp" / f"sub_{i}.png"; im.save(dst); return dst


def build_final(project, music=None):
    """Mux: master_raw + VO por toma (adelay al inicio de cada toma) + subs quemados + música opcional."""
    if not project.master_raw.is_file():
        return {"error": "falta master_raw (corré build_master_raw primero)"}
    tomas = sorted(project.tomas, key=lambda t: t["n"])
    td = [_dur(project.shot_path(t["n"])) for t in tomas]
    starts = [sum(td[:i]) for i in range(len(tomas))]
    VID = _dur(project.master_raw)
    subs = [_render_sub(project, i, t.get("vo", "")) for i, t in enumerate(tomas)]
    # índices de inputs ffmpeg: 0 = master_raw, luego VO, subs y música
    inp = ["-i", str(project.master_raw)]; idx = 1; vo_map = {}
    for i in range(len(tomas)):
        vp = project.vo_path(i)
        if vp.is_file():
            inp += ["-i", str(vp)]; vo_map[i] = idx; idx += 1
    sub_map = {}
    for i, s in enumerate(subs):
        if s:
            inp += ["-loop", "1", "-i", str(s)]; sub_map[i] = idx; idx += 1
    music_idx = None
    if music and pathlib.Path(music).is_file():
        inp += ["-stream_loop", "-1", "-i", str(music)]; music_idx = idx; idx += 1

    fg = ""; prev = "0:v"
    for i in sub_map:
        a = starts[i] + 0.15; b = min(starts[i] + max(_dur(project.vo_path(i)), 2.2) + 0.4, starts[i] + td[i] + 1.0)
        fg += f"[{prev}][{sub_map[i]}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[o{i}];"; prev = f"o{i}"
    fg += f"[{prev}]format=yuv420p[vout];"
    va = []
    for i, vidx in vo_map.items():
        ms = int(starts[i] * 1000); fg += f"[{vidx}:a]adelay={ms}|{ms}[va{i}];"; va.append(f"[va{i}]")
    if va:
        fg += "".join(va) + f"amix=inputs={len(va)}:normalize=0[voice];"
        fg += f"[voice]apad=whole_dur={VID:.3f}[voicep];"
        aout = "[voicep]"
        if music_idx is not None:
            fg += f"[{music_idx}:a]volume=0.12,atrim=0:{VID:.3f}[mus];[voicep][mus]amix=inputs=2:duration=first:normalize=0[aout];"
            aout = "[aout]"
    else:
        aout = None
    cmd = ["ffmpeg", "-y"] + inp + ["-filter_complex", fg.rstrip(";"),
           "-map", "[vout]"] + (["-map", aout] if aout else []) + \
          ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24"] + \
          (["-c:a", "aac", "-b:a", "192k", "-shortest"] if aout else []) + [str(project.master)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"error": r.stderr[-900:]}
    return {"ok": True, "duration": _dur(project.master)}


def run(project, music=None):
    """GO final gateado: sin STALE + todas aprobadas → master_raw → VO → master."""
    ready = deps.assembly_ready(project)
    print(f"== assemble :: ready={ready['ready']} (aprobadas={ready['all_approved']}, "
          f"stale={ready['stale']}, pendientes={ready['pending']}) ==")
    if not ready["ready"]:
        print("  GATE: el armado no procede hasta que no haya STALE y todas las tomas estén aprobadas.")
        return {"gated": True, **ready}
    mr = build_master_raw(project)
    if "error" in mr:
        print("  ", mr["error"]); return mr
    synth_vo(project)
    if not falx.paid_enabled():
        print("  (DRY: VO no sintetizada; el mux del master final requiere VO real.)"); return {"dry": True}
    fin = build_final(project, music=music or project.data.get("music"))
    print("  master.mp4:", fin); return fin
