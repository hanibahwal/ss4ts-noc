import {
  API_BASE_URL,
} from './api'


const DEFAULT_TIMEOUT = 90000


function clampPercent(value) {
  const numericValue = Number(value)

  if (!Number.isFinite(numericValue)) {
    return 0
  }

  return Math.max(
    0,
    Math.min(numericValue, 100),
  )
}


function normalizeSource(
  name,
  source,
) {
  return {
    name,
    available:
      Boolean(source?.available),
    status:
      source?.status ||
      (
        source?.available
          ? 'available'
          : 'unavailable'
      ),
    error:
      source?.error ||
      null,
  }
}


function normalizeFinding(
  finding,
  index,
) {
  return {
    id:
      finding?.code ||
      `finding-${index}`,

    code:
      finding?.code ||
      'UNKNOWN',

    title:
      finding?.title ||
      'Network finding',

    severity:
      finding?.severity ||
      'info',

    message:
      finding?.message ||
      '',

    metric:
      finding?.metric ||
      null,

    value:
      finding?.value ??
      null,

    threshold:
      finding?.threshold ??
      null,

    recommendation:
      finding?.recommendation ||
      '',
  }
}


export async function fetchNetworkIntelligence(
  ip,
  {
    includeHistory = true,
    historyMinutes = 15,
    historyWindowSeconds = 10,
    signal,
  } = {},
) {
  if (!ip) {
    throw new Error(
      'عنوان الجهاز غير متوفر',
    )
  }

  const searchParams =
    new URLSearchParams({
      include_history:
        String(
          Boolean(includeHistory),
        ),

      history_minutes:
        String(historyMinutes),

      history_window_seconds:
        String(historyWindowSeconds),
    })

  const controller =
    new AbortController()

  const timeoutId =
    globalThis.setTimeout(
      () => controller.abort(),
      DEFAULT_TIMEOUT,
    )

  const abortFromParent = () => {
    controller.abort()
  }

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener(
        'abort',
        abortFromParent,
        {
          once: true,
        },
      )
    }
  }

  try {
    const endpoint =
      `/api/v1/devices/` +
      `${encodeURIComponent(ip)}/` +
      `network-intelligence?` +
      searchParams.toString()

    const response =
      await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
          signal:
            controller.signal,

          headers: {
            Accept:
              'application/json',
          },
        },
      )

    if (!response.ok) {
      let detail =
        `HTTP ${response.status}`

      try {
        const body =
          await response.json()

        detail =
          body?.detail ||
          detail
      } catch {
        // Keep default message.
      }

      throw new Error(
        `تعذر تحميل Network Intelligence: ${detail}`,
      )
    }

    return await response.json()
  } finally {
    globalThis.clearTimeout(
      timeoutId,
    )

    if (signal) {
      signal.removeEventListener(
        'abort',
        abortFromParent,
      )
    }
  }
}


export function normalizeNetworkIntelligence(
  response,
) {
  const collector =
    response?.collector ||
    {}

  const analysis =
    response?.analysis ||
    {}

  const device =
    collector?.device ||
    {}

  const traffic =
    collector?.traffic ||
    {}

  const ping =
    collector?.ping ||
    {}

  const lte =
    collector?.lte ||
    {}

  const sourceMap =
    collector?.sources ||
    {}

  const sources =
    Object.entries(sourceMap)
      .map(
        ([name, source]) =>
          normalizeSource(
            name,
            source,
          ),
      )

  const findings =
    Array.isArray(
      analysis?.findings,
    )
      ? analysis.findings.map(
          normalizeFinding,
        )
      : []

  const recommendations =
    Array.isArray(
      analysis?.recommendations,
    )
      ? analysis.recommendations
      : []

  const healthScore =
    clampPercent(
      response?.health_score ??
      analysis?.overall_health_score,
    )

  const confidencePercent =
    clampPercent(
      response?.confidence_percent ??
      analysis?.confidence_percent,
    )

  return {
    raw: response,

    routerIp:
      response?.router_ip ||
      collector?.router_ip ||
      '',

    generatedAt:
      response?.generated_at ||
      collector?.generated_at ||
      null,

    status:
      response?.status ||
      analysis?.overall_health ||
      'unknown',

    healthScore,
    confidencePercent,

    collectorStatus:
      collector?.status ||
      'unknown',

    mode:
      collector?.mode ||
      'unknown',

    summary: {
      availableSources:
        Number(
          collector?.summary
            ?.available_sources,
        ) || 0,

      unavailableSources:
        Number(
          collector?.summary
            ?.unavailable_sources,
        ) || 0,

      totalSources:
        Number(
          collector?.summary
            ?.total_sources,
        ) ||
        sources.length,

      selectedInterface:
        collector?.summary
          ?.selected_interface ||
        traffic?.selected_interface ||
        '',

      currentTotalBps:
        Number(
          collector?.summary
            ?.current_total_bps,
        ) ||
        Number(
          traffic?.total_bps,
        ) ||
        0,

      activeInterfaceCount:
        Number(
          collector?.summary
            ?.active_interface_count,
        ) || 0,
    },

    device: {
      reachable:
        Boolean(device?.reachable),

      identity:
        device?.identity ||
        null,

      boardName:
        device?.board_name ||
        null,

      routerosVersion:
        device?.routeros_version ||
        null,

      cpuUsagePercent:
        device?.cpu_usage_percent ??
        null,

      memoryUsagePercent:
        device?.memory_usage_percent ??
        null,

      temperatureCelsius:
        device?.temperature_celsius ??
        null,

      uptime:
        device?.uptime ||
        null,
    },

    traffic: {
      selectedInterface:
        traffic?.selected_interface ||
        '',

      rxBps:
        Number(traffic?.rx_bps) || 0,

      txBps:
        Number(traffic?.tx_bps) || 0,

      totalBps:
        Number(traffic?.total_bps) || 0,

      trend:
        analysis?.components
          ?.traffic
          ?.details
          ?.trend ||
        'unknown',

      historyPoints:
        Number(
          analysis?.components
            ?.traffic
            ?.details
            ?.history_points,
        ) ||
        (
          Array.isArray(
            traffic?.history?.points,
          )
            ? traffic.history.points.length
            : 0
        ),
    },

    ping: {
      available:
        Boolean(ping?.available),

      reachable:
        Boolean(ping?.reachable),

      latencyMs:
        ping?.latency_ms ??
        null,

      packetLossPercent:
        ping?.packet_loss_percent ??
        null,

      minimumLatencyMs:
        ping?.minimum_latency_ms ??
        null,

      maximumLatencyMs:
        ping?.maximum_latency_ms ??
        null,
    },

    lte: {
      available:
        Boolean(lte?.available),

      rsrp:
        lte?.rsrp ??
        null,

      rsrq:
        lte?.rsrq ??
        null,

      sinr:
        lte?.sinr ??
        null,

      rssi:
        lte?.rssi ??
        null,

      band:
        lte?.band ||
        null,

      operator:
        lte?.operator ||
        null,

      dataClass:
        lte?.data_class ||
        null,

      cellId:
        lte?.cell_id ||
        null,
    },

    sources,
    findings,
    recommendations,

    analyzer: {
      name:
        analysis?.analyzer?.name ||
        '',

      version:
        analysis?.analyzer?.version ||
        '',
    },

    service: {
      name:
        response?.service?.name ||
        '',

      version:
        response?.service?.version ||
        '',
    },
  }
}
