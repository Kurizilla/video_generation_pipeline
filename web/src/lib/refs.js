// Convierte un File a dataURL (para adjuntar referencias/recortes a la edición).
export function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = reject
    r.readAsDataURL(file)
  })
}

// Pega una imagen del portapapeles como dataURL (o null si no hay).
export async function pasteImage() {
  try {
    const items = await navigator.clipboard.read()
    for (const it of items) {
      for (const type of it.types) {
        if (type.startsWith('image/')) {
          const blob = await it.getType(type)
          return await fileToDataUrl(blob)
        }
      }
    }
  } catch { /* sin permiso */ }
  return null
}
