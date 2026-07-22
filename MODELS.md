# MODELS — modelos por etapa y cómo cambiarlos

Los modelos por defecto (endpoints verificados a jul-2026) viven en `pipeline/config.py` →
`DEFAULT_MODELS`, y **se pueden sobreescribir por proyecto** en `project.json → models` o por variable
de entorno. Ningún endpoint está hardcodeado dentro de la lógica de las etapas.

## Por etapa

| Rol (`DEFAULT_MODELS`) | Endpoint por defecto (fal.ai) | Usado en | Notas |
|---|---|---|---|
| `image_hifi` | `fal-ai/gemini-3-pro-image-preview/edit` | anclas + keyframes (alta fidelidad) | Nano Banana Pro, hasta 2 refs, ~$0.15 |
| `image_multi` | `fal-ai/nano-banana-2/edit` | regen completa multi-referencia | hasta ~14 refs, ~$0.06 |
| `inpaint` | `fal-ai/flux-general/inpainting` | edición local por máscara (Modo B) | `mask_url` + `reference_image_url` + `strength` + `seed`, ~$0.05 |
| `video` | `bytedance/seedance-2.0/image-to-video` | shots i2v (principal) | first+last frame; resoluciones 480p/720p/1080p/4k; dur 4–15s |
| `video_fallback` | `fal-ai/kling-video/v3/pro/image-to-video` | shots i2v (fallback) | `start_image_url`+`end_image_url`+`cfg_scale`; sin filtro de likeness de ByteDance |

**Voz en off:** ElevenLabs REST (`pipeline/tts.py`), modelo `eleven_v3` con fallback
`eleven_multilingual_v2`; voz por defecto `cgSgspJ2msm6clMCkdW9` ("Jessica"), override en
`project.json → voice_id` o `config.DEFAULT_VOICE_ID`.

## El filtro de Seedance (i2v)

ByteDance Seedance aplica un chequeo de "likeness de personas reales" que **no se puede desactivar**
(verificado en la documentación de fal). Puede rechazar tomas con multitudes de caras semi-realistas
aunque las imágenes sean 100% generadas. Estrategias:
1. **Estilizar** las caras en los keyframes (más "animado", menos foto-realista), o
2. marcar la toma en `project.json → content_blocked_tomas` para que use el **fallback Kling v3 pro**,
   que no tiene ese filtro.

El código en `pipeline/shots.py` / `pipeline/falx.py` maneja la diferencia de nombres de parámetros
entre Seedance (`image_url`/`end_image_url`/`resolution`) y Kling (`start_image_url`/`end_image_url`/`cfg_scale`).

## Cómo cambiar un modelo

**Por proyecto** (recomendado) — en `project.json`:
```json
{
  "models": {
    "video": "fal-ai/kling-video/v3/pro/image-to-video",
    "image_hifi": "fal-ai/nano-banana-2/edit"
  }
}
```
`config.models(project_data)` mergea estos overrides sobre `DEFAULT_MODELS`.

**Global** — editá `DEFAULT_MODELS` en `pipeline/config.py`.

## Costos (estimados, para el candado)

`config.py` calcula un costo **estimado** antes de gastar (`est_image_cost`, `est_video_cost`):
video por segundo según resolución (`VIDEO_PRICE_PER_S`), Kling por bloque de 5s (`KLING_PRICE_PER_5S`),
imagen por modelo (`IMAGE_PRICE`). Son estimaciones para mostrar en dry-run —
**verificá siempre en [fal.ai/pricing](https://fal.ai/pricing)**. Timeouts en `TIMEOUT_IMAGE` /
`TIMEOUT_VIDEO` para que un cuelgue del modelo se corte y se reporte como error en vez de colgar el server.
