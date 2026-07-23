# PIPELINE — etapas, reglas y contrato de API

Referencia técnica del pipeline. Para el "qué es / cómo instalar / quickstart" ver
[`README.md`](README.md); para modelos ver [`MODELS.md`](MODELS.md).

Cada etapa es un módulo de `pipeline/` con una función `run(project, ...)`, invocable por CLI
(`python -m pipeline <etapa> --project ...`) o desde la API (`POST /api/stage/<name>`). **Todas
respetan el candado de costo**: sin `LOOP_ALLOW_PAID=1` corren en dry-run e informan el costo estimado
sin llamar a ningún modelo.

---

## Etapas

### 1. `anchors` — personajes + sets (hojas de anclaje)
- **Módulo:** `pipeline/anchors.py`
- **Consume:** `project.json → anchors` (`{id: {prompt, refs}}`) + imágenes de `captures/`.
- **Produce:** `out/anchors/<id>.png` — hojas de modelo de personajes y sets.
- **Regla (STYLE LOCK):** las anclas son la **base de consistencia**. Todos los keyframes se anclan a
  ellas por referencia, de modo que el estilo/personaje se mantenga estable en todo el corto.

### 2. `keyframes` — keyframes seam-aware
- **Módulo:** `pipeline/keyframes.py`
- **Consume:** `project.json → keyframes` (`{stem: {prompt, refs}}`), con refs que apuntan a anclas u
  otras imágenes.
- **Produce:** `out/keyframes/shots/<stem>.png` y `out/keyframes/seams/<stem>.png`, más
  `out/keyframes/keyframes_meta.json`.
- **Regla de EMPALME (seam compartido):** cuando `end` de la toma N es igual al `start` de la toma
  N+1, ese keyframe se genera **una sola vez** y se comparte. Garantiza **cortes invisibles** entre
  tomas y ahorra generación. El plan de seams se deriva automáticamente de las tomas
  (`Project.seam_plan()` / `unique_keyframes()`).
- **Regla de texto:** los prompts piden **no** incrustar texto legible (los textos se agregan después
  como overlays), porque los modelos de imagen lo renderizan mal.

### 3. `shots` — image-to-video por toma
- **Módulo:** `pipeline/shots.py`
- **Consume:** cada toma de `project.json → tomas` + sus keyframes `start`/`end`.
- **Produce:** `out/shots_raw/toma<NN>.mp4` + `out/shots_raw/shots_meta.json`.
- **Regla (guardarraíles):** el i2v usa el keyframe `start` como **primer frame** y el `end` como
  **último frame** (`image_url` + `end_image_url`), de modo que el movimiento quede acotado entre dos
  imágenes ya aprobadas. Modelo principal **Seedance 2.0**; fallback **Kling v3 pro** para tomas que el
  filtro de contenido de ByteDance rechaza (marcadas en `content_blocked_tomas`). Ver [`MODELS.md`](MODELS.md).

### 4. `deps` — grafo keyframe→video + STALE
- **Módulo:** `pipeline/deps.py`
- **Produce (solo lectura):** `graph` (qué keyframe alimenta qué toma), `to_regen` (qué falta) y
  `assembly_ready` (si se puede armar el master).
- **Regla (propagación):** editar/aceptar un keyframe marca como **`STALE`** todos los videos que lo
  usan (incluidos los dos lados de un seam compartido). El master no se puede armar con tomas `STALE`.

### 5. Post-producción — 4 pasos DISCRETOS (reemplaza el `assemble` encadenado)
- **Módulo:** `pipeline/postprod.py` (el viejo `assemble.py` queda como helpers ffmpeg + CLI legacy).
- **Manifiesto:** `out/postprod.json` — una entrada por paso, versionada, cada versión guarda su
  `dep_sig` (firma de insumos). Estado por paso: `pending` / `ready` / `stale`.
- **Pasos (cada uno con botón, artefacto versionado y gate propios; reintentables por separado):**
  1. **`unify`** (gratis): concat de shots aprobados → `post/unified.vN.mp4` + timeline de cortes.
     STALE si cambia una versión/estado de shot.
  2. **`vo`** (paga): una línea por toma (`tomas[].vo`, editable) → ElevenLabs, timeada a los cortes del
     unificado → `post/vo.vN/` + `post/vo_script.vN.json`. Idempotente (cachea por línea). Respeta el
     candado (`vo_prep` = plan + costo estimado sin gastar). STALE si cambia `unify`.
     - **Scheduling sin solapamiento:** cada línea arranca en su toma pero nunca antes de que termine la
       anterior (+`VO_GAP`), así dos voces jamás se pisan (fluidez). El `start` agendado se guarda en el
       script (subs y master lo leen → quedan en sync). El artefacto incluye un **QA** (`_vo_qa`):
       `overlap_free`, corrimiento por línea (avisa las que quedaron muy corridas → acortar texto),
       y `tail_overflow` si la VO se pasa del largo del video.
     - **Asistente `vo_distribute`** (opcional, usa LLM `pipeline/llm.py`): pega un guion en PROSA y la IA
       lo reparte en 1 línea por toma según título/acción/duración de cada toma. Solo texto (sin tonos ni
       pausas). Requiere `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` + server en PAGA. Puebla las casillas; el
       usuario revisa antes de sintetizar.
  3. **`subs`** (gratis): SRT verbatim desde el script temporizado de la VO → `post/subs.vN.srt`,
     editable a mano (nueva versión). STALE si cambia `vo`.
  4. **`master`** (gratis): mux unificado + VO (adelay por toma) + subtítulos (overlays PNG, sin libass)
     + música → `post/master.vN.mp4` (+ copia a `out/master.mp4`). **Gate:** solo si 1-3 están `ready` y
     ninguno `stale`.
- **STALE aguas abajo:** regenerar un shot → `unify` stale; re-unificar → `vo` stale; nueva VO → `subs` y
  `master` stale. El front dice qué rehacer. Todo versionado y revertible (`revert(step, v)`).

### Edición (usada por el front, no es una etapa CLI)
- **Módulo:** `pipeline/editing.py`
- **Keyframes:** `kf_regen_one` / `kf_variants` (Modo A = regen completa con comentario+refs;
  Modo B = edición local por máscara con inpainting), `kf_accept` (versiona y propaga STALE),
  `kf_revert`.
- **Videos:** `vid_regen_one` / `vid_variants` (Seedance/Kling, prompt editable), `vid_accept`,
  `vid_revert`, `vid_set_status`.
- **Versionado no destructivo:** cada aceptación preserva la versión previa en `out/_versions/`
  (copia byte-exacta); el histórico de variantes queda en el manifiesto. Todo es revertible.

---

## `project.json`

```jsonc
{
  "name": "example",
  "aspect_ratio": "16:9",
  "style": "…descripción de estilo/render que se inyecta a los prompts…",
  "voice_id": "cgSgspJ2msm6clMCkdW9",          // ElevenLabs (opcional; default en config.py)
  "content_blocked_tomas": [],                  // tomas que van por el fallback Kling
  "models": { },                                // overrides opcionales (ver MODELS.md)

  "anchors": {                                  // personajes + sets → out/anchors/<id>.png
    "hero_sheet": { "prompt": "…", "refs": ["captures/hero_ref.png"] }
  },
  "keyframes": {                                // 1 por borde de toma; refs = anclas u otras imgs
    "shot01_start": { "prompt": "…", "refs": ["style_plate"] },
    "seam_01-02":   { "prompt": "…", "refs": ["room_sheet", "hero_sheet"] }
  },
  "tomas": [                                    // el corto, toma por toma
    { "n": 1, "title": "Apertura",
      "start": "shot01_start", "end": "seam_01-02",   // stems de keyframes
      "duration": 5, "static": false,
      "motion": "descripción del movimiento de cámara/acción para el i2v",
      "vo": "línea de voz en off de esta toma" }
  ]
}
```

**Referencias (`refs`)** se resuelven así (`Project.resolve_ref`): si el string es un id de ancla →
`out/anchors/<id>.png`; si empieza con `captures/` o es un archivo existente → ruta del proyecto; si no,
ruta literal. Un **seam compartido** se declara simplemente usando el **mismo stem** como `end` de una
toma y `start` de la siguiente.

---

## Contrato de API (`pipeline/server.py`, FastAPI)

Base por defecto `http://localhost:8788` (config del front: `VITE_API_BASE`). Los assets generados se
sirven en `GET /out/<ruta relativa a project.out>` (sigue symlinks, con guarda anti `..`).

### Lectura / estado
| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/api/project` | nombre, aspect, `paid` (candado), lista de anchors, nº de tomas |
| GET | `/api/tomas` | tomas con su estado |
| GET | `/api/kf/{stem}` | meta de un keyframe (versiones, current, last_error, deps) |
| GET | `/api/vid/{key}` | meta de una toma (start/end refs, status, versiones) |
| GET | `/api/kf/variants/{stem}` · `/api/vid/variants/{key}` | histórico de variantes |
| GET | `/api/deps/graph` · `/api/deps/to-regen` · `/api/deps/for/{stem}` | grafo y STALE |
| GET | `/api/assembly-ready` | si se puede armar el master |

### Etapas y armado
| Método | Ruta | Cuerpo |
|---|---|---|
| POST | `/api/stage/{name}` | `{only?}` — dispara anchors/keyframes/shots |
| POST | `/api/assemble` | GO encadenado legacy (unificación + VO + subs) |

### Post-producción (4 pasos discretos)
| Método | Ruta | Nota |
|---|---|---|
| GET | `/api/post/state` | estado + versiones + artefacto de cada paso; `master.can_build` |
| POST | `/api/post/unify` | PASO 1 (job en background) |
| POST | `/api/post/vo/prep` | PASO 2 plan + costo estimado (no gasta) |
| POST | `/api/post/vo/distribute` | PASO 2 asistente IA: `{prose}` → `{lines:{n:texto}}` |
| POST | `/api/post/vo` | PASO 2 síntesis (job; paga si `LOOP_ALLOW_PAID`) |
| POST · PUT | `/api/post/subs` | PASO 3 generar · editar (nueva versión) |
| POST | `/api/post/master` | PASO 4 (gate 1-3 ready+no stale; job) |
| POST | `/api/post/revert` | `{step, v}` — revertir cualquier paso |
| GET | `/api/job/{jid}` | estado de un job de post-producción |

### Edición (jobs async: devuelven `job_id`, se sondea `.../status/{jid}`)
| Método | Ruta | Cuerpo |
|---|---|---|
| POST | `/api/kf/regen` | `{stem, mode:A|B, num_variants, ref_images, comment/instruction, hifi, mask_png, strength}` |
| POST | `/api/kf/accept` · `/api/kf/revert` | `{stem, variant_path/v, note?}` |
| POST | `/api/vid/regen` | `{key, comment, overrides:{prompt,duration,model,resolution/cfg_scale}, num_variants}` |
| POST | `/api/vid/accept` · `/api/vid/revert` · `/api/vid/set-status` | `{key, …}` |

### Reemplazo manual (multipart — subir archivo local)
| Método | Ruta | Form-data |
|---|---|---|
| POST | `/api/kf/upload` | `stem`, `file` (imagen) — versiona el keyframe y marca STALE dependientes |
| POST | `/api/vid/upload` | `key`, `file` (video) — versiona la toma y la deja aprobada |
| POST | `/api/anchor/upload` | `id`, `file` (imagen) — respalda la anterior y reemplaza el ancla |

Los endpoints de regen son **asíncronos** (job + polling) para no bloquear el HTTP mientras fal genera;
persisten `last_error` si el modelo falla o se cuelga (timeouts en `config.py`).
