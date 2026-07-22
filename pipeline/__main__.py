"""CLI del pipeline:  python -m pipeline <etapa> --project projects/<nombre> [opciones]

  anchors    genera personajes + sets (hojas de anclaje)
  keyframes  genera keyframes (seam-aware) + manifiesto
  shots      genera el video de cada toma (i2v first+last)
  deps       imprime el grafo keyframe→video + qué falta regenerar
  assemble   [GO] unificación → VO → subtítulos → master (gateado)
  serve      levanta la API para el front React

Sin LOOP_ALLOW_PAID=1, todo corre en DRY-RUN sin gastar.
"""
import argparse, json
from . import project as prj


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    ap.add_argument("stage", choices=["anchors", "keyframes", "shots", "deps", "assemble", "serve"])
    ap.add_argument("--project", required=True, help="ruta a projects/<nombre>")
    ap.add_argument("--only", nargs="*", help="anchors/keyframes: solo estos ids/stems")
    ap.add_argument("--tomas", nargs="*", type=int, help="shots: solo estas tomas")
    ap.add_argument("--port", type=int, default=8777)
    a = ap.parse_args()
    p = prj.load(a.project)

    if a.stage == "anchors":
        from . import anchors; anchors.run(p, only=a.only)
    elif a.stage == "keyframes":
        from . import keyframes; keyframes.run(p, only=a.only)
    elif a.stage == "shots":
        from . import shots; shots.run(p, which=a.tomas)
    elif a.stage == "assemble":
        from . import assemble; assemble.run(p)
    elif a.stage == "deps":
        from . import deps
        print(json.dumps({"graph": deps.graph(p), "to_regen": deps.to_regen(p),
                          "assembly_ready": deps.assembly_ready(p)}, ensure_ascii=False, indent=2))
    elif a.stage == "serve":
        from . import server; server.serve(p, port=a.port)


if __name__ == "__main__":
    main()
