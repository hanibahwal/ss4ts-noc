const API_BASE_URL =
  import.meta.env.VITE_API_URL || ''

const DEFAULT_TIMEOUT_MS = 15000

function buildEndpoint(
  ip,
  {
    interfaceName = '',
    minutes = 15,
    windowSeconds = 10,
  } = {},
) {
  const searchParams = new URLSearchParams({
    minutes: String(minutes),
    window: String(windowSeconds),
  })

  if (interfaceName) {
    searchParams.set(
      'interface',
      interfaceName,
    )
  }

  return (
    `${API_BASE_URL}/api/v1/devices/` +
    `${encodeURIComponent(ip)}/` +
    `decision-intelligence?` +
    searchParams.toString()
  )
}

async function readErrorMessage(
  response,
) {
  let message =
    `Decision Intelligence API error: ` +
    `HTTP ${response.status}`

  try {
    const body = await response.json()

    if (body?.detail) {
      message = String(body.detail)
    }
  } catch {
    // Keep the HTTP fallback message.
  }

  return message
}

export async function fetchDecisionIntelligence(
  ip,
  {
    interfaceName = '',
    minutes = 15,
    windowSeconds = 10,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
  } = {},
) {
  if (!ip) {
    throw new Error(
      'عنوان الجهاز غير متوفر',
    )
  }

  const controller =
    new AbortController()

  let abortedByTimeout = false

  const timeout = window.setTimeout(
    () => {
      abortedByTimeout = true
      controller.abort()
    },
    timeoutMs,
  )

  function abortFromExternalSignal() {
    controller.abort()
  }

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener(
        'abort',
        abortFromExternalSignal,
        {
          once: true,
        },
      )
    }
  }

  try {
    const response = await fetch(
      buildEndpoint(
        ip,
        {
          interfaceName,
          minutes,
          windowSeconds,
        },
      ),
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
        signal: controller.signal,
      },
    )

    if (!response.ok) {
      throw new Error(
        await readErrorMessage(
          response,
        ),
      )
    }

    return await response.json()
  } catch (error) {
    if (
      error?.name === 'AbortError'
    ) {
      if (abortedByTimeout) {
        throw new Error(
          'انتهت مهلة تحليل القرار',
        )
      }

      throw error
    }

    throw error
  } finally {
    window.clearTimeout(timeout)

    if (signal) {
      signal.removeEventListener(
        'abort',
        abortFromExternalSignal,
      )
    }
  }
}

export function getRiskLevel(
  data,
) {
  return (
    data?.risk?.level ||
    data?.overall_risk ||
    'unknown'
  )
}

export function getRiskScore(
  data,
) {
  const value = Number(
    data?.risk?.score ?? 0,
  )

  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(
    0,
    Math.min(value, 100),
  )
}

export function getPrimaryChain(
  data,
) {
  return {
    signal:
      data?.top_signal ||
      data?.signals?.[0] ||
      null,

    rootCause:
      data?.root_causes?.[0] ||
      null,

    recommendation:
      data?.recommendations?.[0] ||
      null,

    decision:
      data?.decisions?.[0] ||
      null,
  }
}

export function getDataQuality(
  data,
) {
  const context =
    data?.analysis_context || {}

  return {
    quality:
      context.traffic_quality ||
      'unknown',

    completenessPercent:
      Number(
        context
          .traffic_completeness_percent ??
        0,
      ),

    sampleCount:
      Number(
        context
          .traffic_sample_count ??
        0,
      ),

    partialData:
      Boolean(
        data?.request_context
          ?.partial_data,
      ),

    sources:
      data?.data_sources || {},
  }
}

export function normalizeDecisionIntelligence(
  data,
) {
  const safeData =
    data && typeof data === 'object'
      ? data
      : {}

  const chain = getPrimaryChain(
    safeData,
  )

  return {
    ...safeData,

    routerIp:
      safeData.router_ip || '',

    deviceName:
      safeData.device_name ||
      safeData.router_ip ||
      'Unknown Device',

    riskLevel:
      getRiskLevel(safeData),

    riskScore:
      getRiskScore(safeData),

    executiveSummary:
      safeData.executive_summary ||
      safeData.summary ||
      '',

    chain,

    dataQuality:
      getDataQuality(safeData),

    signals: Array.isArray(
      safeData.signals,
    )
      ? safeData.signals
      : [],

    rootCauses: Array.isArray(
      safeData.root_causes,
    )
      ? safeData.root_causes
      : [],

    recommendations:
      Array.isArray(
        safeData.recommendations,
      )
        ? safeData.recommendations
        : [],

    decisions: Array.isArray(
      safeData.decisions,
    )
      ? safeData.decisions
      : [],

    statistics:
      safeData.statistics || {},

    explainability:
      safeData.explainability || {},

    domainIntegration:
      safeData.domain_integration ||
      {},
  }
}
