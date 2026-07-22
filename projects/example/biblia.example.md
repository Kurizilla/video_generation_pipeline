# Biblia (ejemplo) — proyecto `example`

> Documento de referencia humana. La biblia describe el concepto, los personajes, los sets y las tomas.
> El pipeline se dirige por `project.json` (que codifica lo mismo en forma operable). Para un proyecto real,
> reemplazá esta biblia + `captures/` + `project.json` con los de tu concepto.

## Concepto
Un cortometraje corto de 3 tomas para demostrar el pipeline de punta a punta.

## Personajes (Anexo A)
- **Hero** — protagonista. (Poné su descripción fija; se repite en cada prompt para consistencia.)
- **Guide** — mascota/guía del hero.

## Set (Anexo B)
- **Room** — sala recurrente; debe verse idéntica en todas las tomas de interior.

## Tomas
1. **Apertura** — plano amplio del mundo → push-in a la sala, encontramos al Hero.
2. **El encuentro** — aparece el Guide junto al Hero; ambos reaccionan.
3. **Cierre** — Hero y Guide miran a cámara juntos.

Los empalmes (`seam_01-02`, `seam_02-03`) son **frames compartidos**: el END de una toma es el START de la
siguiente (corte invisible por construcción).
