import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  fetchDecisionIntelligence,
  normalizeDecisionIntelligence,
} from '../services/decisionIntelligence'


export default function useDecisionIntelligence(
  ip,
  {
    interfaceName = '',
    minutes = 15,
    windowSeconds = 10,
    refreshInterval = 30000,
    enabled = true,
  } = {},
) {
  const [
    data,
    setData,
  ] = useState(null)

  const [
    loading,
    setLoading,
  ] = useState(false)

  const [
    refreshing,
    setRefreshing,
  ] = useState(false)

  const [
    error,
    setError,
  ] = useState(null)

  const [
    lastUpdated,
    setLastUpdated,
  ] = useState(null)

  const requestIdRef = useRef(0)

  const abortControllerRef =
    useRef(null)

  const mountedRef = useRef(true)

  const load = useCallback(
    async ({
      silent = false,
    } = {}) => {
      if (!enabled || !ip) {
        return null
      }

      requestIdRef.current += 1

      const requestId =
        requestIdRef.current

      if (
        abortControllerRef.current
      ) {
        abortControllerRef.current
          .abort()
      }

      const controller =
        new AbortController()

      abortControllerRef.current =
        controller

      if (silent) {
        setRefreshing(true)
      } else {
        setLoading(true)
      }

      setError(null)

      try {
        const result =
          await fetchDecisionIntelligence(
            ip,
            {
              interfaceName,
              minutes,
              windowSeconds,
              signal:
                controller.signal,
            },
          )

        if (
          !mountedRef.current ||
          requestId !==
            requestIdRef.current
        ) {
          return null
        }

        const normalized =
          normalizeDecisionIntelligence(
            result,
          )

        setData(normalized)
        setLastUpdated(new Date())

        return normalized
      } catch (requestError) {
        if (
          requestError?.name ===
          'AbortError'
        ) {
          return null
        }

        if (
          mountedRef.current &&
          requestId ===
            requestIdRef.current
        ) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'تعذر تحميل تحليل القرار',
          )
        }

        return null
      } finally {
        if (
          mountedRef.current &&
          requestId ===
            requestIdRef.current
        ) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [
      enabled,
      interfaceName,
      ip,
      minutes,
      windowSeconds,
    ],
  )

  const refresh = useCallback(
    () =>
      load({
        silent: Boolean(data),
      }),
    [
      data,
      load,
    ],
  )

  useEffect(() => {
    mountedRef.current = true

    if (!enabled || !ip) {
      setData(null)
      setError(null)
      setLoading(false)
      setRefreshing(false)

      return undefined
    }

    load()

    return () => {
      if (
        abortControllerRef.current
      ) {
        abortControllerRef.current
          .abort()
      }
    }
  }, [
    enabled,
    ip,
    interfaceName,
    minutes,
    windowSeconds,
    load,
  ])

  useEffect(() => {
    if (
      !enabled ||
      !ip ||
      !refreshInterval ||
      refreshInterval < 5000
    ) {
      return undefined
    }

    const intervalId =
      window.setInterval(
        () => {
          load({
            silent: true,
          })
        },
        refreshInterval,
      )

    return () => {
      window.clearInterval(
        intervalId,
      )
    }
  }, [
    enabled,
    ip,
    refreshInterval,
    load,
  ])

  useEffect(
    () => () => {
      mountedRef.current = false

      if (
        abortControllerRef.current
      ) {
        abortControllerRef.current
          .abort()
      }
    },
    [],
  )

  return {
    data,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh,

    riskLevel:
      data?.riskLevel ||
      'unknown',

    riskScore:
      data?.riskScore || 0,

    executiveSummary:
      data?.executiveSummary ||
      '',

    primarySignal:
      data?.chain?.signal ||
      null,

    primaryRootCause:
      data?.chain?.rootCause ||
      null,

    primaryRecommendation:
      data?.chain
        ?.recommendation ||
      null,

    primaryDecision:
      data?.chain?.decision ||
      null,

    dataQuality:
      data?.dataQuality ||
      null,
  }
}
