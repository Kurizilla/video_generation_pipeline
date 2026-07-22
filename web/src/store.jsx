import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { api } from './api'

const Ctx = createContext(null)

export function StoreProvider({ children }) {
  const [project, setProject] = useState(null)
  const [tomas, setTomas] = useState([])
  const [toRegen, setToRegen] = useState({ stale: [], pending: [] })
  const [ready, setReady] = useState({ ready: false, all_approved: false, stale: [], pending: [] })
  const [toast, setToast] = useState('')
  const [jobs, setJobs] = useState([])
  const doneSeen = useRef(new Set())   // jids ya completados → detectar transición a "listo"

  const refresh = useCallback(async () => {
    try {
      const [t, tr, r] = await Promise.all([api.tomas(), api.toRegen(), api.assemblyReady()])
      setTomas(t); setToRegen(tr); setReady(r)
    } catch (e) { setToast('No se pudo contactar la API (' + API_HINT + ')') }
  }, [])

  useEffect(() => { api.project().then(setProject).catch(() => setToast('API no responde')); refresh() }, [refresh])

  // Poller global de la cola de jobs (para el tracker de la esquina). Al completarse uno, refresca estado.
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const { jobs: js } = await api.jobs()
        if (!alive) return
        setJobs(js || [])
        const nowDone = (js || []).filter((j) => j.done).map((j) => j.jid)
        const fresh = nowDone.filter((j) => !doneSeen.current.has(j))
        if (fresh.length) { fresh.forEach((j) => doneSeen.current.add(j)); refresh() }  // algo terminó → actualizar STALE/estado
      } catch { /* API caída: reintenta al próximo tick */ }
    }
    const id = setInterval(tick, 2500); tick()
    return () => { alive = false; clearInterval(id) }
  }, [refresh])

  const clearJobs = useCallback(async () => { await api.jobsClear(); setJobs((j) => j.filter((x) => !x.done)) }, [])

  const flash = useCallback((msg) => { setToast(msg); setTimeout(() => setToast(''), 4000) }, [])

  return (
    <Ctx.Provider value={{ project, tomas, toRegen, ready, refresh, toast, flash, jobs, clearJobs }}>
      {children}
    </Ctx.Provider>
  )
}
const API_HINT = 'levantá pipeline.server y revisá VITE_API_BASE'
export const useStore = () => useContext(Ctx)
