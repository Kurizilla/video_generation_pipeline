# captures/ — insumos de referencia del proyecto

Poné aquí las **imágenes de referencia crudas** que anclan la identidad (personajes/sets), referenciadas
desde `project.json` → `anchors[*].refs` (p.ej. `captures/hero_ref.png`).

Para el proyecto de ejemplo, los refs son **opcionales**: si no existen, la etapa `anchors` genera igual
desde el prompt (sin anclaje). Para calidad/consistencia real, agregá:

- `hero_ref.png` — referencia del personaje protagonista
- `guide_ref.png` — referencia del guía/mascota
- `room_ref.png` — referencia del set/sala

**Livianas** (unos cientos de KB). Las de proyectos reales/pesadas quedan **fuera del repo** (este dir está
gitignoreado salvo `projects/example/captures/`). Nunca subas assets pesados ni material con datos privados.
