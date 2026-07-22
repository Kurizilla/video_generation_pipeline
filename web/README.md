# web/ — Front del pipeline (React + Vite)

UI para operar el pipeline **end-to-end**: navegar personajes/sets, keyframes y shots; editar keyframes
(Modo A regen completa · Modo B máscara con referencias/recortes); regenerar el video de cada plano;
ver la dependencia keyframe→video con **STALE**; y el **GO** final (unificación → VO → subtítulos → master),
habilitado solo cuando no queda nada STALE y todas las tomas están aprobadas.

## Stack
- React 18 + Vite. Sin secretos en el front (la FAL_KEY vive en el backend `pipeline.server`).
- Estado en `src/store.jsx` (Context). Cliente de API en `src/api.js`.

## Correr
```bash
# 1) backend (API del pipeline) — en el repo raíz:
LOOP_ALLOW_PAID=1 python -m pipeline serve --project projects/<nombre> --port 8788
# 2) front:
cd web && npm install
cp .env.example .env.local     # ajustá VITE_API_BASE si el backend no está en :8788
npm run dev                    # http://localhost:5173
npm run build                  # build de producción → web/dist/
```

## Etapas (UI)
| Vista | Qué hace |
|---|---|
| Personajes / Sets | previews de anclas + generar faltantes (STYLE LOCK) |
| Keyframes | timeline seam-aware + **editor A/B** (refs/recortes, máscara, variantes, versiones, revertir) |
| Shots | por toma: video + START/END + regen (modelo Seedance/Kling, prompt editable, controles) + aprobar |
| Master | gate + GO (assemble) + preview del master |

## Contrato de API (consumido; ver `src/api.js`)
- `GET /api/project` · `GET /api/tomas` · `GET /api/deps/{graph,to-regen,for/{stem}}` · `GET /api/assembly-ready`
- `GET /api/kf/{stem}` · `GET /api/vid/{key}` · `GET /api/{kf,vid}/variants/{id}`
- Regen async: `POST /api/{kf,vid}/regen` → `{job_id}`; `GET /api/{kf,vid}/status/{jid}` (polling)
- `POST /api/{kf,vid}/accept` · `POST /api/{kf,vid}/revert` · `POST /api/vid/set-status`
- `POST /api/stage/{anchors|keyframes|shots}` · `POST /api/assemble`
- Assets generados: `GET /out/<ruta>` (imágenes/videos servidos por el backend).

Aceptar un keyframe marca **STALE** los videos que lo usan (empalme = 2); el banner y el badge lo reflejan.
