# video-pipeline

Pipeline para generar **cortos animados** (estilo Pixar) a partir de un guion, con IA — de punta a
punta y **parametrizable por proyecto**. Genera hojas de personajes/sets, keyframes con empalmes
compartidos, videos por toma (image-to-video), y arma el master final con voz en off y subtítulos.
Incluye un **front React** para conducir todo el flujo (revisar, editar, regenerar, aprobar).

- **Imagen / video:** [fal.ai](https://fal.ai) (Nano Banana Pro / Gemini image edit, FLUX inpainting,
  ByteDance Seedance 2.0 y Kling v3 para i2v).
- **Voz en off:** [ElevenLabs](https://elevenlabs.io).
- **Candado de costo:** nada se gasta a menos que `LOOP_ALLOW_PAID=1`. Sin eso, todo corre en **dry-run**.

> Documentos relacionados: [`PIPELINE.md`](PIPELINE.md) (cada etapa + contrato de API),
> [`MODELS.md`](MODELS.md) (modelos por etapa y cómo cambiarlos), [`SECURITY.md`](SECURITY.md)
> (secretos y candado de costo), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`RELEASE_PLAN.md`](RELEASE_PLAN.md).

---

## Arquitectura (de un vistazo)

```
guion/biblia
   │
   ▼
[anchors]  personajes + sets  →  hojas de anclaje (STYLE LOCK)
   │
   ▼
[keyframes]  1 imagen por borde de toma; los EMPALMES son compartidos
   │          (end de la toma N == start de la toma N+1 → corte invisible)
   ▼
[shots]  image-to-video por toma, usando start+end como guardarraíles (first/last frame)
   │
   ▼
[assemble]  unificar + voz en off (ElevenLabs) + subtítulos + música  →  master.mp4
```

Un **grafo de dependencias** keyframe→video marca como `STALE` los videos cuyo keyframe cambió, y el
botón final **GO** (unificación) solo se habilita cuando no queda nada `STALE`.

Cada etapa es **project-agnóstica**: lee todo de `projects/<nombre>/` (ver
[Parametrización](#parametrización-por-proyecto)). No hay nada de un proyecto concreto hardcodeado.

---

## Requisitos

- **Python 3.9+** y **Node 18+** (para el front).
- **ffmpeg** en el `PATH` (se usa para concatenar/mezclar el master).
- Cuentas con saldo en **fal.ai** y **ElevenLabs** (solo si vas a generar de verdad; el dry-run no requiere saldo).

---

## Instalación

```bash
# 1) Backend (paquete Python)
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                                        # instala el paquete `pipeline`

# 2) Credenciales (ver SECURITY.md)
cp .env.example .env
#   editá .env y pegá FAL_KEY y ELEVENLABS_API_KEY

# 3) Front (React + Vite)
cd web && npm install && cp .env.example .env          # VITE_API_BASE=http://localhost:8788
cd ..
```

---

## Quickstart (con el proyecto de ejemplo, sin gastar)

```bash
# 1) Ver el grafo de dependencias del proyecto de ejemplo
python -m pipeline deps --project projects/example

# 2) Dry-run de cada etapa (NO gasta: no está LOOP_ALLOW_PAID)
python -m pipeline anchors   --project projects/example
python -m pipeline keyframes --project projects/example
python -m pipeline shots     --project projects/example

# 3) Levantar la API + el front
python -m pipeline serve --project projects/example --port 8788
#   en otra terminal:
cd web && npm run dev        # abre http://localhost:5173
```

Para **generar de verdad** (gasta dinero), antepone el candado a cada comando:

```bash
LOOP_ALLOW_PAID=1 python -m pipeline anchors --project projects/example
```

En el front, el estado `PAGA / DRY` se muestra en el header; el servidor se levanta con
`LOOP_ALLOW_PAID=1 python -m pipeline serve ...` para habilitar el gasto desde la UI.

---

## Uso — CLI

```
python -m pipeline <etapa> --project projects/<nombre> [opciones]

  anchors     genera personajes + sets (hojas de anclaje).   --only <ids...>
  keyframes   genera keyframes (seam-aware) + manifiesto.     --only <stems...>
  shots       genera el video de cada toma (i2v first+last).  --tomas <n...>
  deps        imprime el grafo keyframe→video + qué falta regenerar.
  assemble    [GO] unificación → VO → subtítulos → master (gateado).
  serve       levanta la API para el front React.             --port 8788
```

Sin `LOOP_ALLOW_PAID=1` todo corre en **dry-run** e informa el costo estimado.

## Uso — Front React

El front (`web/`) cubre el flujo completo: navegar personajes/sets/keyframes/tomas, disparar cada
etapa, **editor de keyframes** (regen completa o edición local por máscara, con referencias/recortes),
**regen de video por toma** (Seedance/Kling, prompt editable), **reemplazo manual** (subir tu propia
imagen o video local), grafo con `STALE` y panel de "qué falta regenerar", y el botón **GO** final.
Ver [`web/README.md`](web/README.md) y el contrato de API en [`PIPELINE.md`](PIPELINE.md).

---

## Parametrización por proyecto

Todo proyecto vive en `projects/<nombre>/`:

```
projects/<nombre>/
├── project.json      # personajes/sets (anchors), keyframes (prompts+refs), tomas, voz, modelos
├── biblia.md         # guion/biblia (referencia humana; opcional)
├── captures/         # imágenes de referencia crudas (livianas; las reales van fuera del repo)
└── out/              # TODO lo generado (gitignored): anchors, keyframes, shots, vo, master, versiones
```

`projects/example/` es un proyecto mínimo y liviano que sirve de plantilla. Para arrancar uno nuevo,
copialo, editá `project.json` (personajes, tomas, prompts, voz) y poblá `captures/`. La estructura de
`project.json` está documentada en [`PIPELINE.md`](PIPELINE.md#projectjson).

> El proyecto real "El Salvador Aprende" **no** se incluye en el repo (IP + assets pesados); vive como
> carpeta de proyecto externa siguiendo esta misma estructura.

---

## Seguridad y costo

- **Secretos** solo por variables de entorno (`.env`, gitignored). Nunca se commitean. Ver [`SECURITY.md`](SECURITY.md).
- **Candado de costo**: sin `LOOP_ALLOW_PAID=1`, ninguna etapa llama a un modelo pago.
- El `.gitignore` excluye `.env*`, `node_modules/`, `.venv/`, todas las salidas generadas
  (`out/`, `*.mp4/*.mp3`, `_versions/`, etc.) y los `captures/` de proyectos (salvo el ejemplo).

## Licencia

Uso interno GOES. Los modelos de terceros (fal.ai, ElevenLabs) tienen sus propios términos y costos.
