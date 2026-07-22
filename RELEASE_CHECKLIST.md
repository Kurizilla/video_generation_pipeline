# RELEASE CHECKLIST — verificación de entrega

Checklist para confirmar que el repo es entregable a otro técnico: liviano, seguro, documentado y
capaz de correr de punta a punta. Ver el plan completo en [`RELEASE_PLAN.md`](RELEASE_PLAN.md).

## Seguridad
- [x] `.env` **no** está trackeado (`git ls-files | grep '^.env$'` vacío).
- [x] Sin valores de secreto en el árbol ni en el historial (repo nuevo desde cero; historia limpia).
- [x] Sin secretos hardcodeados en el código (`pipeline/*.py` usan `os.environ` / `load_dotenv`).
- [x] `.gitignore` cubre `.env*`, `*.key/*.pem/*credentials*`, `node_modules/`, `.venv/`, `*.egg-info/`,
      media generada (`*.mp4/*.mov/*.mp3/*.wav`), salidas (`out/`, `_versions/`, `_tmp/`, …) y
      `captures/` de proyectos (salvo el ejemplo).
- [x] `.env.example` completo (FAL_KEY, ELEVENLABS_API_KEY + config/opcionales).
- [x] `SECURITY.md` documenta qué var usa cada servicio y el candado de costo.

## Peso / contenido
- [x] No se suben assets pesados ni salidas generadas (0 archivos `*.mp4/*.mp3` staged).
- [x] Árbol de trabajo liviano (código + docs, MB no GB).
- [x] El proyecto real "El Salvador Aprende" queda **fuera** del repo (IP + assets); se documenta como
      proyecto externo con la misma estructura.
- [x] Solo `projects/example/` (mínimo, liviano) va incluido como plantilla.

## Documentación
- [x] `README.md` (qué es, arquitectura, requisitos, instalación, quickstart, CLI + front, parametrización).
- [x] `PIPELINE.md` (cada etapa: consume/produce/reglas/gates + `project.json` + contrato de API).
- [x] `MODELS.md` (modelos fal/ElevenLabs por etapa, filtro de Seedance, cómo cambiarlos, costos).
- [x] `SECURITY.md`, `CONTRIBUTING.md`, `RELEASE_PLAN.md`.

## Funcionalidad verificada
- [x] Candado de costo: sin `LOOP_ALLOW_PAID=1` todas las etapas corren en dry-run sin gastar.
- [x] Pipeline project-agnóstico: cada etapa lee de `projects/<nombre>/project.json`.
- [x] API levanta (`python -m pipeline serve`) y expone lectura, etapas, edición async y **upload manual**
      (keyframe / video / personajes-sets) — rutas presentes (HTTP 422 sin args, no 404).
- [x] Front React compila (`npm run build` → 42 módulos, sin errores).
- [x] Reemplazo manual (subir imagen/video local) disponible en keyframes, shots y personajes/sets.

## Onboarding limpio (para reproducir)
```bash
git clone <repo> && cd video-pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env            # (sin llaves aún, el dry-run igual valida el cableado)
python -m pipeline deps --project projects/example
python -m pipeline keyframes --project projects/example      # dry-run, no gasta
cd web && npm install && cp .env.example .env && npm run build
```
- [ ] (a ejecutar por quien recibe) clon limpio en máquina nueva → seguir README → dry-run OK → front levanta.
