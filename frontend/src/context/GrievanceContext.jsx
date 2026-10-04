import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import { createGrievance, listGrievances, updateGrievance } from '../services/api'
import { DONE_MESSAGE, FLOW, SECTIONS } from '../components/data/flow'

const Ctx = createContext(null)
export const useGrievance = () => useContext(Ctx)

function snapshotFrom(grievance) {
  return {
    title: grievance.title,
    step: grievance.step,
    messages: grievance.messages,
    entries: grievance.entries,
  }
}

export function GrievanceProvider({ children }) {
  const { user, loading: authLoading } = useAuth()
  const [loadedUserId, setLoadedUserId] = useState(null)
  const [storedGrievances, setStoredGrievances] = useState([])
  const [storedCurrent, setStoredCurrent] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [reportOpen, setReportOpen] = useState(false)

  useEffect(() => {
    let active = true
    if (authLoading || !user?.id) return () => { active = false }
    listGrievances()
      .then((records) => {
        if (!active) return
        setLoadedUserId(user.id)
        setStoredGrievances(records)
        setStoredCurrent(records[0] || null)
        setError('')
      })
      .catch((requestError) => {
        if (active) {
          setLoadedUserId(user.id)
          setError(requestError.message)
          setStoredGrievances([])
          setStoredCurrent(null)
        }
      })

    return () => {
      active = false
    }
  }, [authLoading, user])

  const loading = authLoading || Boolean(user?.id && loadedUserId !== user.id)
  const grievances = user?.id === loadedUserId ? storedGrievances : []
  const current = user?.id === loadedUserId ? storedCurrent : null

  const persist = useCallback(async (recordId, snapshot) => {
    setSaving(true)
    setError('')
    try {
      const saved = await updateGrievance(recordId, snapshot)
      setStoredCurrent(saved)
      setStoredGrievances((records) => [saved, ...records.filter((record) => record.id !== saved.id)])
      return saved
    } catch (requestError) {
      setError(requestError.message)
      return null
    } finally {
      setSaving(false)
    }
  }, [])

  const start = useCallback(async (text) => {
    const snapshot = {
      title: text.slice(0, 255),
      step: 0,
      messages: [{ from: 'user', text }, { from: 'ai', text: FLOW[0].ai }],
      entries: [{ title: 'What happened', text }],
    }
    setSaving(true)
    setError('')
    try {
      const saved = await createGrievance(snapshot)
      setLoadedUserId(user.id)
      setStoredCurrent(saved)
      setStoredGrievances((records) => [saved, ...records])
      setReportOpen(false)
      return saved
    } catch (requestError) {
      setError(requestError.message)
      throw requestError
    } finally {
      setSaving(false)
    }
  }, [user])

  const pick = useCallback(async (option) => {
    if (!current || current.step >= FLOW.length || saving) return
    const currentFlowStep = FLOW[current.step]
    const nextStep = currentFlowStep.next ? currentFlowStep.next(option) : current.step + 1
    const reply = nextStep < FLOW.length ? FLOW[nextStep].ai : DONE_MESSAGE
    const next = {
      ...snapshotFrom(current),
      step: nextStep,
      messages: [...current.messages, { from: 'user', text: option }, { from: 'ai', text: reply }],
      entries: currentFlowStep.entry && (!currentFlowStep.entryIf || currentFlowStep.entryIf(option))
        ? [...current.entries, currentFlowStep.entry]
        : current.entries,
    }
    return Boolean(await persist(current.id, next))
  }, [current, persist, saving])

  const ask = useCallback(async (text) => {
    if (!current || saving) return
    const next = {
      ...snapshotFrom(current),
      messages: [
        ...current.messages,
        { from: 'user', text },
        { from: 'ai', text: 'Good question. This guided workflow can use the details already saved in your report.' },
      ],
    }
    return Boolean(await persist(current.id, next))
  }, [current, persist, saving])

  const open = useCallback((record) => {
    setStoredCurrent(record)
    setReportOpen(false)
  }, [])

  const entries = current?.entries || []
  const step = current?.step || 0
  const isDone = step >= FLOW.length
  const stage = FLOW[Math.min(step, FLOW.length - 1)].stage
  const options = !current || isDone ? [] : FLOW[step]?.options || []
  const done = SECTIONS.filter((section) => entries.some((entry) => entry.title === section.key)).length
  const progress = useMemo(
    () => ({ done, total: SECTIONS.length, percent: Math.round((done / SECTIONS.length) * 100) }),
    [done],
  )

  const value = {
    grievances,
    loading,
    saving,
    error,
    currentId: current?.id ?? null,
    started: current !== null,
    title: current?.title || '',
    messages: current?.messages || [],
    entries,
    stage,
    options,
    progress,
    reportOpen,
    setReportOpen,
    start,
    pick,
    ask,
    open,
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
