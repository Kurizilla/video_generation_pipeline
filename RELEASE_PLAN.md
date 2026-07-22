# RELEASE_PLAN — repo entregable del pipeline de generación de video

## Context
El repo actual (`video_generation_pipeline`, 11 GB) quedó desordenado tras mucho debugging: mezcla el
pipeline **nuevo** que construimos esta sesión (`out_esaprende/`, hoy **untracked**) con un orquestador
**legacy "Nora"** (`stages/`, único código **trackeado**) y ~9 GB de salidas de otros proyectos
(`loop/`, `out_b2*`, `out_leoleo_story`, `out_aprenderaleer`, `out/`). Objetivo: **un repo nuevo, liviano,
seguro y documentado** para que OTRO técnico corra el pipeline de punta a punta para **cualquier
concepto/video**, con un front React bien hecho.

**Decisiones del cliente (Fase 0):** (1) el pipeline **nuevo** es el core; legacy y demás `out_*/loop`
se **archivan fuera** del repo. (2) **Parametrizar por proyecto** (`projects/<nombre>/`). (3) **Repo nuevo
desde cero** (historia fresca).

> Este archivo ES el entregable de la Fase 0. Al aprobarse, lo copio como `RELEASE_PLAN.md` en el repo nuevo
> y ejecuto **fase por fase, parando al final de cada una**. Nada destructivo sin OK explícito en su paso.

---

## Auditoría (Fase 0, read-only) — hallazgos

### Inventario (tamaños)
| Área | Tamaño | Git | Qué es |
|---|---|---|---|
| `out_esaprende/` código | **284 KB** | untracked | **Pipeline NUEVO** (core del entregable): `gen_anchors/keyframes/shots(_kling)`, `edit_lib/vid_lib/deps`, `unified_server` + `studio.html`/`editor.html`/`video_editor.html`/`review.html`, `build_master/build_meta/vo_synth/assemble_final(_vo)`, `shots_meta`, docs |
| `out_esaprende/` assets | 750 MB (329) | untracked | keyframes, shots, vo, masters, `_versions/_tmp/_snapshots` → **generados** |
| `stages/ core/ runner/ manifest/` | 891 MB | **tracked** | Orquestador **legacy Nora** (13 etapas) — a **archivar** |
| `videos/` (3 mp4) | 140 MB | **tracked** | Demos legacy — **NO SUBIR** |
| `samples/` | 7.7 MB | tracked | Assets legacy |
| `loop/ out_b2 out_b2_film out_b2_film_v2 out_leoleo_story out_aprenderaleer out/` | ~8.9 GB | untracked (`out/` ignored) | Otros proyectos/salidas — **archivar/NO SUBIR** |

### Seguridad
- ✅ Solo **2 commits**; `.env` **nunca** commiteado (solo `.env.example`). Escaneo de historial: **sin valores
  de secreto** (los `xi-api-key` hallados son código que referencia la env var).
- ✅ **Sin secretos hardcodeados** en el código nuevo (`out_esaprende/*.py` usan `os.environ`/`load_dotenv`).
- ✅ **Sin rutas absolutas** `/Users/...` en archivos trackeados.
- ⚠️ Secretos reales viven SOLO en disco (no en git): `.env` (FAL_KEY, ELEVENLABS_API_KEY, OPENAI, ANTHROPIC,
  GCP) y `loop/.env.loop` (2º FAL_KEY con saldo). **No deben migrar** al repo nuevo.
- **Repo nuevo ⇒ no hace falta reescribir historia ni rotar llaves** (nada quedó expuesto). Se documenta igual.

### Clasificación SUBIR / NO SUBIR / DUDOSO
- **SUBIR:** código del pipeline (refactor de `out_esaprende/*.py`), front React (`web/`), docs, `.env.example`,
  `requirements.txt`/config versionable (endpoints fal, voz ElevenLabs — sin secretos), `projects/example/`
  (insumos mínimos livianos o placeholders + README).
- **NO SUBIR:** `.env`, `loop/.env.loop`, cualquier credencial; TODOS los assets generados (keyframes/shots/
  vo/masters/`_versions`/`_tmp`/`_snapshots`); `out_*/`, `loop/`; `videos/` (3 demos 140 MB); `node_modules/`,
  `.venv/`, caches, `.DS_Store`, logs.
- **DUDOSO (el cliente decide en su fase):** el proyecto real **"El Salvador Aprende"** (biblia + `captures_b2/`
  refs de personajes + master final) → propuesta: mantenerlo **fuera del repo** (IP/pesado), como carpeta de
  proyecto privada/externa, no en el repo público. Las hojas de anclaje/keyframes finales como referencia:
  fuera (pesadas); se pueden publicar aparte si se quiere.

---

## Estructura final propuesta del repo
```
video-pipeline/                     # repo nuevo, liviano
├── README.md  PIPELINE.md  MODELS.md  SECURITY.md  CONTRIBUTING.md  RELEASE_CHECKLIST.md
├── .gitignore  .env.example  requirements.txt  pyproject.toml
├── pipeline/                       # paquete Python generalizado (refactor de out_esaprende)
│   ├── config.py                   # carga config de proyecto + endpoints fal + voces (sin secretos)
│   ├── falx.py                     # wrappers fal (subscribe con TIMEOUT) + candado de costo LOOP_ALLOW_PAID
│   ├── anchors.py                  # etapa PERSONAJES + SETS (ex gen_anchors)
│   ├── keyframes.py                # etapa KEYFRAMES + plan de seams + START/END (ex gen_keyframes)
│   ├── deps.py                     # grafo keyframe→video + STALE/propagación de empalme
│   ├── shots.py                    # etapa SHOTS i2v Seedance/Kling first+last (ex gen_shots/_kling)
│   ├── editing.py                  # edición keyframe (Modo A/B) + regen video por plano (ex edit_lib/vid_lib)
│   ├── assemble.py                 # unificación → VO (ElevenLabs) → subtítulos → pegado + slates
│   └── server.py                   # API unificada (FastAPI) — reemplaza los http.server prototipo
├── web/                            # app React (Vite) — front del pipeline completo
│   └── src/… (components, api client, state, env)
├── projects/
│   └── example/                    # proyecto de ejemplo mínimo (liviano)
│       ├── project.json            # personajes, tomas, voz, aspect, duraciones
│       ├── biblia.example.md       # guion/biblia de muestra (corto)
│       └── captures/               # refs livianas o placeholders + README de cómo poblar
└── scripts/                        # CLIs: run_anchors / run_keyframes / run_shots / assemble
```
- **Parametrización:** cada etapa recibe `--project projects/<nombre>` y lee `project.json` + `captures/` +
  `biblia`. El actual "El Salvador" se documenta como el proyecto de referencia (fuera del repo).
- **Config versionable (sin secretos):** endpoints fal por defecto — imagen `gemini-3-pro-image-preview/edit`
  + `nano-banana-2/edit`, inpaint `flux-general/inpainting`, video `seedance-2.0/image-to-video` (+ fallback
  `kling-video/v3/pro`), voz ElevenLabs `Jessica`. Todo override-able por `project.json`/env.

---

## Fases de ejecución (cada una PARA al final para tu revisión)

**FASE 1 — Seguridad y secretos.** Reconfirmar 0 secretos en el material a migrar; escribir `.env.example`
(FAL_KEY, ELEVENLABS_API_KEY, opcionales OPENAI/ANTHROPIC/GCP) + `SECURITY.md` (qué var usa cada servicio,
candado de costo). Nota: repo nuevo ⇒ sin scrub de historia ni rotación (nada expuesto). *Entrega: reporte
de seguridad. Gate.*

**FASE 2 — Repo nuevo + `.gitignore`.** Inicializar el repo nuevo (carpeta aparte, historia fresca), escribir
`.gitignore` robusto (`.env*`, `out_*/`, `projects/*/captures/`, assets generados `*.mp4/*.mp3/*.png` bajo
salidas, `node_modules/`, `.venv/`, caches). Verificar que **nada sensible/pesado** quede staged. *Gate.*

**FASE 3 — Reestructura + parametrización (núcleo).** Portar `out_esaprende/*.py` a `pipeline/` como paquete
**project-agnóstico**: extraer `config.py`/`falx.py` (con **timeout** ya incorporado), reemplazar textos/paths
hardcodeados de "El Salvador" por lectura de `project.json`/`biblia`/`captures`; crear `projects/example/`
mínimo; CLIs en `scripts/`. Mantener las reglas aprendidas (anclaje, seams compartidos, STYLE LOCK, filtro de
texto, edición local, deps/STALE, mismo modelo i2v). *Entrega: pipeline corre con el ejemplo en DRY. Gate.*

**FASE 4 — Documentación.** `README.md` (qué es, arquitectura, requisitos, instalación, env, cómo correr
pipeline + front, quickstart con el ejemplo), `PIPELINE.md` (cada etapa, consume/produce, gates, reglas),
`MODELS.md` (fal imagen/video + ElevenLabs, endpoint por etapa, cómo cambiarlo), `SECURITY.md`,
`CONTRIBUTING.md`. *Gate.*

**FASE 5 — Front React.** Reescribir la MISMA UX de `studio.html` como app React (Vite) limpia:
navegar personajes/sets/keyframes/shots; disparar por etapa; editor de keyframes (regen completa + máscara con
refs/recortes); regen de video por plano; grafo keyframe→video con **STALE** y panel "qué falta regenerar";
botón **GO** final (unificación+audios+subs+pegado) habilitado solo sin STALE. Estado bien manejado, contrato
de API documentado, env, build/run reproducible, parametrizable por proyecto, sin secretos. *Gate.*

**FASE 6 — Verificación de entrega.** Simular onboarding: clon limpio → seguir README → correr el pipeline
con `projects/example` (DRY/no-spend donde se pueda) → levantar el front. Checklist de seguridad (sin
secretos en árbol/historial, `.gitignore` ok, `.env.example` completo) y de tamaño (liviano).
*Entrega: `RELEASE_CHECKLIST.md` marcado.*

---

## Verificación (cómo se prueba al final)
- `pip install -r requirements.txt` en venv limpio; `python -m pipeline.<etapa> --project projects/example`
  en modo DRY (sin `LOOP_ALLOW_PAID`) → no gasta y valida el cableado de cada etapa.
- `cd web && npm ci && npm run build` reproducible; `npm run dev` levanta el front contra la API.
- **Clon limpio** en carpeta temporal → seguir sólo el README → confirmar que corre sin los assets reales.
- `git grep` de patrones de secreto + tamaño del repo (`du -sh`, debe ser MB, no GB).

## Alcance / reglas
- Ejecuto **una fase a la vez** y **paro** al terminar cada una para mostrarte el resultado.
- Nada destructivo sobre el repo actual (no borro `out_*/` ni reescribo su historia). El repo entregable es
  **nuevo y aparte**; el actual queda como archivo. Borrado/rotación/`git rm` solo con tu OK en ese paso.
- Sin subir assets pesados, videos, audios, salidas generadas ni secretos.
