# SECURITY

## Secretos y variables de entorno
Todos los secretos van por **variables de entorno** (archivo `.env` local, **gitignored**). Nunca se
hardcodean ni se commitean. Copiá `.env.example` → `.env` y completá:

| Variable | Servicio | Requerida | Usada en |
|---|---|---|---|
| `FAL_KEY` | fal.ai | ✅ | imagen (keyframes/edición) + video (shots i2v) — `pipeline/falx.py` |
| `ELEVENLABS_API_KEY` | ElevenLabs | ✅ (para audio) | voz en off — `pipeline/assemble.py` |
| `LOOP_ALLOW_PAID` | — (candado de costo) | no (default off) | habilita llamadas pagas; sin ella, todo corre en **dry-run** sin gastar |
| `SHOT_RES` | — (config) | no | resolución de shots (480p/720p/1080p/4k) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GCP_*` | — | no | opcionales / no usadas por el core actual |

## Candado de costo (importante)
El pipeline hace llamadas **pagas** a fal.ai y ElevenLabs. Por diseño, **no gasta un centavo** salvo que
`LOOP_ALLOW_PAID=1` esté seteado. En dry-run muestra qué haría (modelo, costo estimado) sin llamar al modelo.
Revisá siempre el costo estimado antes de habilitar el gasto.

## Reglas
- **Nunca** commitear `.env`, llaves, tokens ni credenciales. El `.gitignore` excluye `.env*` (salvo
  `.env.example`), `*.key`, `*.pem`, `*credentials*.json`.
- **Nunca** subir assets pesados ni salidas generadas (ver `.gitignore`): quedan fuera del repo.
- Rotá las llaves si sospechás exposición. **Este repo se creó desde cero**: su historial no contiene
  secretos (verificado), así que no requirió limpieza de historia ni rotación al momento de la entrega.

## Verificación
```bash
# no debe haber valores de secreto en el árbol ni en el historial:
git grep -nE "FAL_KEY=[A-Za-z0-9]|ELEVENLABS_API_KEY=[A-Za-z0-9]|sk-[A-Za-z0-9]{16}" $(git rev-list --all) || echo "limpio"
# .env no debe estar trackeado:
git ls-files | grep -E "^\.env$" && echo "PELIGRO: .env trackeado" || echo ".env no trackeado ✓"
```
