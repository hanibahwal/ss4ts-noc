import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  fetchExecutiveNarrative,
  normalizeExecutiveNarrative,
} from '../services/executiveNarrative'


export default function useExecutiveNarrative(
  ip,
  {
    includeHistory = true,
    historyMinutes = 15,
    historyWindowSeconds = 10,
    refreshInterval = 30000,
    enabled = true,
  } = {},
) {


  const [data, setData] =
    useState(null)


  const [loading, setLoading] =
    useState(false)


  const [
    refreshing,
    setRefreshing,
  ] = useState(false)


  const [error, setError] =
    useState('')


  const [
    lastUpdated,
    setLastUpdated,
  ] = useState(null)



  const requestIdRef =
    useRef(0)


  const abortControllerRef =
    useRef(null)


  const mountedRef =
    useRef(true)




  const load =
    useCallback(
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



        setError('')



        try {


          const response =
            await fetchExecutiveNarrative(
              ip,
              {
                includeHistory,
                historyMinutes,
                historyWindowSeconds,
                signal:
                  controller.signal,
              },
            )



          /*
            H30.28 Debug
            Check backend payload
          */

          console.log(
            'EXECUTIVE RAW RESPONSE',
            response,
          )

          console.log(
            'HISTORICAL INTELLIGENCE',
            response?.historical_intelligence,
          )



          if (
            !mountedRef.current ||
            requestId !==
              requestIdRef.current
          ) {

            return null

          }




          const normalized =
            normalizeExecutiveNarrative(
              response,
            )



          /*
            H30.28 Debug
            Check frontend normalized data
          */

          console.log(
            'EXECUTIVE NORMALIZED DATA',
            normalized,
          )


          console.log(
            'NORMALIZED HISTORICAL',
            normalized?.historicalIntelligence,
          )




          setData(normalized)


          setLastUpdated(
            new Date(),
          )



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
                : 'تعذر تحميل الملخص التنفيذي',
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
        historyMinutes,
        historyWindowSeconds,
        includeHistory,
        ip,
      ],
    )






  const refresh =
    useCallback(
      () =>
        load({
          silent:
            Boolean(data),
        }),
      [
        data,
        load,
      ],
    )






  useEffect(() => {

    mountedRef.current = true



    if (
      !enabled ||
      !ip
    ) {


      setData(null)

      setError('')

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
      globalThis.setInterval(
        () => {

          load({
            silent: true,
          })


        },
        refreshInterval,
      )




    return () => {


      globalThis.clearInterval(
        intervalId,
      )


    }


  }, [
    enabled,
    ip,
    load,
    refreshInterval,
  ])








  useEffect(
    () =>
      () => {


        mountedRef.current = false



        requestIdRef.current += 1




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

  }


}
