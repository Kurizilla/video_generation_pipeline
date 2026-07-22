import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from './api'

const Ctx = createContext(null)

export function StoreProvider({ children }) {
  const [project, setProject] = useState(null)
  const [tomas, setTomas] = useState([])
  const [toRegen, setToRegen] = useState({ stale: [], pending: [] })
  const [ready, setReady] = useState({ ready: false, all_approved: false, stale: [], pending: [] })
  const [toast, setToast] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [t, tr, r] = await Promise.all([api.tomas(), api.toRegen(), api.assemblyReady()])
      setTomas(t); setToRegen(tr); setReady(r)
    } catch (e) { setToast('No se pudo contactar la API (' + API_HINT + ')') }
  }, [])

  useEffect(() => { api.project().then(setProject).catch(() => setToast('API no responde')); refresh() }, [refresh])

  const flash = useCallback((msg) => { setToast(msg); setTimeout(() => setToast(''), 4000) }, [])

  return (
    <Ctx.Provider value={{ project, tomas, toRegen, ready, refresh, toast, flash }}>
      {children}
    </Ctx.Provider>
  )
}
const API_HINT = 'levantá pipeline.server y revisá VITE_API_BASE'
export const useStore = () => useContext(Ctx)
