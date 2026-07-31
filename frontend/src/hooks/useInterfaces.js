import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { api } from '../services/api'


const DEFAULT_REFRESH_INTERVAL = 15000


function normalizeInterface(
  item,
  index,
) {
  const rxBps =
    Number(item?.rx_bps) || 0

  const txBps =
    Number(item?.tx_bps) || 0

  const speedBps =
    Number(item?.speed_bps) || 0

  const totalBps =
    Number(item?.total_bps) ||
    rxBps + txBps

  const utilizationValue =
    item?.utilization_percent === null ||
    item?.utilization_percent === undefined
      ? null
      : Number(
          item.utilization_percent,
        )

  const utilizationPercent =
    Number.isFinite(
      utilizationValue,
    )
      ? Math.max(
          0,
          Math.min(
            utilizationValue,
            100,
          ),
        )
      : null

  const rxErrors =
    Number(item?.rx_errors) || 0

  const txErrors =
    Number(item?.tx_errors) || 0

  const isAdminUp =
    item?.is_admin_up ??
    item?.admin_status === 'up'

  const isOperUp =
    item?.is_oper_up ??
    item?.oper_status === 'up'

  return {
    ...item,

    if_descr:
      item?.if_descr ||
      item?.name ||
      `interface-${index + 1}`,

    if_index:
      item?.if_index ??
      item?.index ??
      index + 1,

    if_type:
      item?.if_type ||
      'unknown',

    admin_status:
      item?.admin_status ||
      (isAdminUp
        ? 'up'
        : 'down'),

    oper_status:
      item?.oper_status ||
      (isOperUp
        ? 'up'
        : 'down'),

    is_admin_up:
      Boolean(isAdminUp),

    is_oper_up:
      Boolean(isOperUp),

    speed_bps:
      speedBps,

    mtu:
      Number(item?.mtu) || 0,

    rx_bps:
      rxBps,

    tx_bps:
      txBps,

    total_bps:
      totalBps,

    utilization_percent:
      utilizationPercent,

    rx_errors:
      rxErrors,

    tx_errors:
      txErrors,

    total_errors:
      rxErrors + txErrors,

    has_errors:
      Boolean(item?.has_errors) ||
      rxErrors > 0 ||
      txErrors > 0,

    rx_drops:
      item?.rx_drops === null ||
      item?.rx_drops === undefined
        ? null
        : Number(
            item.rx_drops,
          ) || 0,

    tx_drops:
      item?.tx_drops === null ||
      item?.tx_drops === undefined
        ? null
        : Number(
            item.tx_drops,
          ) || 0,

    mac_address:
      item?.mac_address ||
      null,

    last_updated:
      item?.last_updated ||
      item?.time ||
      null,

    last_change:
      item?.last_change ||
      null,
  }
}


function calculateSummary(
  interfaces,
  apiSummary = null,
) {
  const calculated =
    interfaces.reduce(
      (result, item) => {
        result.total += 1

        result.total_rx_bps +=
          item.rx_bps

        result.total_tx_bps +=
          item.tx_bps

        if (item.is_oper_up) {
          result.operational_up += 1
        } else {
          result.operational_down += 1
        }

        if (item.has_errors) {
          result.with_errors += 1
        }

        if (
          item.is_oper_up &&
          item.total_bps > 0
        ) {
          result.active_traffic += 1
        }

        return result
      },
      {
        total: 0,
        operational_up: 0,
        operational_down: 0,
        active_traffic: 0,
        with_errors: 0,
        total_rx_bps: 0,
        total_tx_bps: 0,
      },
    )

  return {
    ...calculated,
    ...(apiSummary || {}),

    total:
      apiSummary?.total !==
      undefined
        ? Number(
            apiSummary.total,
          )
        : calculated.total,

    operational_up:
      apiSummary?.operational_up !==
      undefined
        ? Number(
            apiSummary.operational_up,
          )
        : calculated.operational_up,

    operational_down:
      apiSummary?.operational_down !==
      undefined
        ? Number(
            apiSummary.operational_down,
          )
        : calculated.operational_down,

    with_errors:
      apiSummary?.with_errors !==
      undefined
        ? Number(
            apiSummary.with_errors,
          )
        : calculated.with_errors,

    total_rx_bps:
      apiSummary?.total_rx_bps !==
      undefined
        ? Number(
            apiSummary.total_rx_bps,
          )
        : calculated.total_rx_bps,

    total_tx_bps:
      apiSummary?.total_tx_bps !==
      undefined
        ? Number(
            apiSummary.total_tx_bps,
          )
        : calculated.total_tx_bps,

    active_traffic:
      calculated.active_traffic,
  }
}


export default function useInterfaces({
  ip,
  minutes = 15,
  refreshInterval =
    DEFAULT_REFRESH_INTERVAL,
  enabled = true,
} = {}) {
  const [data, setData] =
    useState(null)

  const [loading, setLoading] =
    useState(true)

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

  const loadInterfaces =
    useCallback(
      async (
        isRefresh = false,
      ) => {
        if (!ip || !enabled) {
          return
        }

        const requestId =
          requestIdRef.current + 1

        requestIdRef.current =
          requestId

        try {
          setError('')

          if (isRefresh) {
            setRefreshing(true)
          } else {
            setLoading(true)
          }

          const result =
            await api.interfaces(
              ip,
              minutes,
            )

          if (
            requestId !==
            requestIdRef.current
          ) {
            return
          }

          setData(result)
          setLastUpdated(
            new Date(),
          )
        } catch (
          requestError
        ) {
          if (
            requestId !==
            requestIdRef.current
          ) {
            return
          }

          console.error(
            'Interfaces request failed:',
            requestError,
          )

          setError(
            requestError?.message ||
            'تعذر تحميل بيانات واجهات الجهاز.',
          )
        } finally {
          if (
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
        ip,
        minutes,
      ],
    )

  useEffect(() => {
    if (!enabled || !ip) {
      setLoading(false)
      return undefined
    }

    loadInterfaces(false)

    const intervalId =
      globalThis.setInterval(
        () => {
          loadInterfaces(true)
        },
        refreshInterval,
      )

    return () => {
      requestIdRef.current += 1

      globalThis.clearInterval(
        intervalId,
      )
    }
  }, [
    enabled,
    ip,
    loadInterfaces,
    refreshInterval,
  ])

  const interfaces =
    useMemo(() => {
      const sourceInterfaces =
        Array.isArray(
          data?.interfaces,
        )
          ? data.interfaces
          : []

      return sourceInterfaces.map(
        normalizeInterface,
      )
    }, [data])

  const summary =
    useMemo(() => {
      return calculateSummary(
        interfaces,
        data?.summary,
      )
    }, [
      data?.summary,
      interfaces,
    ])

  const interfacesByName =
    useMemo(() => {
      return new Map(
        interfaces.map(
          (item) => [
            item.if_descr,
            item,
          ],
        ),
      )
    }, [interfaces])

  function getInterface(
    interfaceName,
  ) {
    return (
      interfacesByName.get(
        interfaceName,
      ) || null
    )
  }

  return {
    data,
    interfaces,
    summary,

    selectedInterface:
      data?.selected_interface ||
      '',

    routerIp:
      data?.router_ip ||
      ip ||
      '',

    loading,
    refreshing,
    error,
    lastUpdated,

    refresh: () =>
      loadInterfaces(true),

    getInterface,
  }
}
