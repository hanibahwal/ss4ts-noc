import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import { api } from '../services/api'


const DEFAULT_REFRESH_INTERVAL = 10000


export default function useTrafficHistory({
  ip,
  interfaceName,
  minutes = 15,
  window: aggregationWindow = 10,
  refreshInterval = DEFAULT_REFRESH_INTERVAL,
  enabled = true,
}) {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const requestIdRef = useRef(0)

  const loadHistory = useCallback(
    async (isRefresh = false) => {
      if (!ip || !enabled) {
        return
      }

      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId

      try {
        setError('')

        if (isRefresh) {
          setRefreshing(true)
        } else {
          setLoading(true)
        }

        const result = await api.trafficHistory(ip, {
          interfaceName,
          minutes,
          window: aggregationWindow,
        })

        if (requestId !== requestIdRef.current) {
          return
        }

        setHistory(result)
        setLastUpdated(new Date())
      } catch (requestError) {
        if (requestId !== requestIdRef.current) {
          return
        }

        console.error(
          'Traffic history request failed:',
          requestError,
        )

        setError('تعذر تحميل سجل حركة الشبكة.')
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [
      ip,
      interfaceName,
      minutes,
      aggregationWindow,
      enabled,
    ],
  )

  useEffect(() => {
    if (!enabled) {
      return undefined
    }

    loadHistory(false)

    const intervalId = globalThis.setInterval(() => {
      loadHistory(true)
    }, refreshInterval)

    return () => {
      requestIdRef.current += 1
      globalThis.clearInterval(intervalId)
    }
  }, [
    enabled,
    loadHistory,
    refreshInterval,
  ])

  return {
    history,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh: () => loadHistory(true),
  }
}
