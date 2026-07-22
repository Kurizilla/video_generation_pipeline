import { forwardRef, useImperativeHandle, useRef, useEffect, useState } from 'react'

// Lienzo de máscara sobre una imagen. Expone getMaskPng()/isEmpty()/clear() al padre vía ref.
const MaskCanvas = forwardRef(function MaskCanvas({ src }, ref) {
  const imgRef = useRef(null)
  const canRef = useRef(null)
  const drawing = useRef(false)
  const [brush, setBrush] = useState(46)

  useEffect(() => {
    const img = imgRef.current
    const fit = () => { const c = canRef.current; if (img && c) { c.width = img.clientWidth; c.height = img.clientHeight } }
    if (img?.complete) fit()
    if (img) img.onload = fit
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [src])

  const paint = (e) => {
    const c = canRef.current, r = c.getBoundingClientRect(), g = c.getContext('2d')
    g.fillStyle = 'rgba(41,224,173,.5)'
    g.beginPath(); g.arc(e.clientX - r.left, e.clientY - r.top, brush / 2, 0, 7); g.fill()
  }
  const clear = () => { const c = canRef.current; c.getContext('2d').clearRect(0, 0, c.width, c.height) }

  useImperativeHandle(ref, () => ({
    clear,
    isEmpty() {
      const c = canRef.current; if (!c) return true
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data
      for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return false
      return true
    },
    getMaskPng() {
      const img = imgRef.current, oc = document.createElement('canvas')
      oc.width = img.naturalWidth; oc.height = img.naturalHeight
      const g = oc.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, oc.width, oc.height)
      const mc = canRef.current
      g.drawImage(mc, 0, 0, mc.width, mc.height, 0, 0, oc.width, oc.height)
      const d = g.getImageData(0, 0, oc.width, oc.height), a = d.data
      for (let i = 0; i < a.length; i += 4) { const on = a[i + 1] > 30 || a[i] > 30; a[i] = a[i + 1] = a[i + 2] = on ? 255 : 0; a[i + 3] = 255 }
      g.putImageData(d, 0, 0); return oc.toDataURL('image/png')
    },
  }))

  return (
    <div>
      <div className="maskwrap">
        <img ref={imgRef} src={src} className="kfimg" crossOrigin="anonymous" alt="" />
        <canvas ref={canRef}
          onMouseDown={(e) => { drawing.current = true; paint(e) }}
          onMouseMove={(e) => { if (drawing.current) paint(e) }}
          onMouseUp={() => (drawing.current = false)}
          onMouseLeave={() => (drawing.current = false)} />
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <span className="muted">pincel</span>
        <input type="range" min="10" max="120" value={brush} onChange={(e) => setBrush(+e.target.value)} style={{ width: 120 }} />
        <button onClick={clear}>limpiar máscara</button>
      </div>
    </div>
  )
})
export default MaskCanvas
