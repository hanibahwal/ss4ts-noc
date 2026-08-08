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


function normalizeObservation(
  observation,
  index,
) {

  return {

    id:
      observation?.code ||
      `observation-${index}`,

    code:
      observation?.code ||
      'UNKNOWN',

    title:
      observation?.title ||
      'ملاحظة تشغيلية',

    severity:
      observation?.severity ||
      'info',

    severityArabic:
      observation?.severity_ar ||
      observation?.severity ||
      'معلومة',

    value:
      observation?.value ??
      null,

    metric:
      observation?.metric ||
      null,

    recommendation:
      observation?.recommendation ||
      '',

  }

}



export async function fetchExecutiveNarrative(
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
      `executive-narrative?` +
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

        // Keep default error

      }



      throw new Error(
        `تعذر تحميل الملخص التنفيذي: ${detail}`,
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






export function normalizeExecutiveNarrative(
  response,
) {


  const metrics =
    response?.metrics ||
    {}



  const observations =
    Array.isArray(
      response?.key_observations,
    )
      ?
        response.key_observations.map(
          normalizeObservation,
        )
      :
        []



  const actions =
    Array.isArray(
      response?.recommended_actions,
    )
      ?
        response.recommended_actions
      :
        []





  /*
    H30.28 Historical Intelligence Mapping

    Backend:
    historical_intelligence

    Frontend:
    historicalIntelligence
  */


  const historicalIntelligence =
    response?.historical_intelligence ||
    {}





  const cpuHistory =
    historicalIntelligence?.cpu ||
    {}





  return {


    routerIp:
      response?.router_ip ||
      '',



    generatedAt:
      response?.generated_at ||
      null,



    status:
      response?.status ||
      'unknown',



    statusArabic:
      response?.status_ar ||
      'غير معروفة',



    healthScore:
      clampPercent(
        response?.health_score,
      ),



    confidencePercent:
      clampPercent(
        response?.confidence_percent,
      ),




    /*
      H30.28 Intelligence Fallback
    */

    headline:
      response?.headline ||
      (
        cpuHistory?.available
          ?
          `تحليل CPU: ${cpuHistory.decision}`
          :
          'الملخص التنفيذي غير متوفر'
      ),




    executiveSummary:
      response?.executive_summary ||
      (
        cpuHistory?.available
          ?
          `التحليل التاريخي: متوسط CPU ${cpuHistory.average}%، أعلى قيمة ${cpuHistory.maximum}%، الاتجاه ${cpuHistory.trend}`
          :
          ''
      ),




    operationalSummary:
      response?.operational_summary ||
      '',



    businessImpact:
      response?.business_impact ||
      '',



    priority:
      response?.priority ||
      'low',



    requiresImmediateAction:
      Boolean(
        response?.requires_immediate_action,
      ),



    observations,



    actions,





    metrics: {


      availableSources:
        Number(
          metrics?.available_sources ||
          0,
        ),



      totalSources:
        Number(
          metrics?.total_sources ||
          0,
        ),



      selectedInterface:
        metrics?.selected_interface ||
        'غير محددة',



      cpuUsagePercent:
        Number(
          metrics?.cpu_usage_percent ||
          0,
        ),



      memoryUsagePercent:
        Number(
          metrics?.memory_usage_percent ||
          0,
        ),



      latencyMs:
        Number(
          metrics?.latency_ms ||
          0,
        ),



      packetLossPercent:
        Number(
          metrics?.packet_loss_percent ||
          0,
        ),


    },





    /*
      H30.28 Historical Intelligence
    */


    historicalIntelligence,




    lteSummary:
      response?.lte_summary ||
      {},




    engine:
      response?.engine ||
      {},


  }

}
