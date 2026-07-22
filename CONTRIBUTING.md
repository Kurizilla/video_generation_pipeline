# CONTRIBUTING

## Entorno de desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env          # pegá FAL_KEY / ELEVENLABS_API_KEY (ver SECURITY.md)

cd web && npm install && cp .env.example .env
```

## Cómo trabajar sin gastar

El candado de costo (`LOOP_ALLOW_PAID`) está **apagado** por defecto: todas las etapas corren en
dry-run e informan el costo estimado sin llamar a ningún modelo pago. Desarrollá y probá el cableado en
dry-run; solo antepone `LOOP_ALLOW_PAID=1` cuando querés generar de verdad.

```bash
python -m pipeline deps --project projects/example          # sanity check del grafo
python -m pipeline keyframes --project projects/example     # dry-run
```

## Estructura del código

- `pipeline/` — paquete Python. Una etapa = un módulo con `run(project, ...)`.
  - `config.py` (modelos/precios/timeouts, sin secretos), `falx.py` (wrappers fal + candado),
    `project.py` (abstracción de proyecto), `anchors/keyframes/shots/deps/assemble/editing/tts`,
    `server.py` (API FastAPI).
- `web/` — front React (Vite). `src/api.js` es el único punto que habla con el backend.
- `projects/example/` — proyecto de referencia mínimo.

## Reglas al contribuir

- **Nunca** commitees secretos ni assets generados. Antes de `git add`, revisá `git status` — el
  `.gitignore` ya excluye `.env*`, `out/`, media (`*.mp4/*.mp3`), `node_modules/`, `.venv/`, versiones y
  `captures/` de proyectos (salvo el ejemplo). Si ves un `.env` o un `.mp4` staged, **pará**.
- **Mantené el pipeline project-agnóstico:** nada de un proyecto concreto hardcodeado en `pipeline/`.
  Todo lo específico va en `projects/<nombre>/project.json`.
- **Respetá el candado de costo:** cualquier llamada paga nueva debe pasar por `falx.ensure_paid()` /
  `falx.paid_enabled()` y tener su rama dry-run con costo estimado.
- **Preservá el versionado no destructivo:** aceptar una edición nunca debe borrar la versión previa
  (se guarda en `out/_versions/`), y todo debe ser revertible.
- **Modelos:** cambialos por `project.json → models` o `config.DEFAULT_MODELS`, no dentro de la lógica.
- Escribí código y comentarios en el mismo estilo del que rodea (español, conciso).

## Estilo de commits

Mensajes claros y en imperativo. No incluyas rutas absolutas ni datos sensibles en el mensaje.

## Verificación antes de un PR / entrega

Ver [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md): clon limpio → README → dry-run del ejemplo →
`npm run build` → chequeos de seguridad y de tamaño del repo.
