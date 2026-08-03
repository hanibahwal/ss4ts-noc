const API_BASE_URL =
  import.meta.env.VITE_API_URL || ''



async function request(
  endpoint,
  options = {},
) {

  const controller =
    new AbortController()


  const timeout =
    globalThis.setTimeout(
      () => controller.abort(),
      10000,
    )


  try {

    const response =
      await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
          ...options,

          headers: {
            'Content-Type':
              'application/json',

            ...options.headers,
          },

          signal:
            controller.signal,
        },
      )


    if (!response.ok) {

      let errorMessage =
        `API error: HTTP ${response.status}`


      try {

        const errorBody =
          await response.json()


        if (errorBody?.detail) {

          errorMessage =
            String(
              errorBody.detail,
            )

        }


      } catch {

        // Keep default HTTP error

      }


      throw new Error(
        errorMessage,
      )

    }


    return await response.json()



  } catch (error) {


    if (
      error.name === 'AbortError'
    ) {

      throw new Error(
        'انتهت مهلة الاتصال بخادم API',
      )

    }


    throw error



  } finally {


    globalThis.clearTimeout(
      timeout,
    )


  }

}





function normalizeDevice(
  device,
) {

  return {

    ...device,


    ip:
      device.ip ||
      device.ip_address,


    name:
      device.name ||
      device.identity ||
      'MikroTik Router',


    type:
      device.type ||
      device.device_type ||
      device.model ||
      'MikroTik RouterOS',


    site:
      device.site ||
      'غير محدد',


    status:
      device.status ||
      'unknown',

  }

}







export const api = {



  health() {

    return request(
      '/api/v1/health',
    )

  },



  systemStatus() {

    return request(
      '/api/system/status',
    )

  },



  async devices() {


    const result =
      await request(
        '/api/devices',
      )


    const devices =
      Array.isArray(result)
        ? result
        : result.devices || []



    return devices.map(
      normalizeDevice,
    )

  },





  async device(
    ip,
  ) {


    const result =
      await request(
        `/api/devices/${encodeURIComponent(ip)}`,
      )


    return normalizeDevice(
      result,
    )

  },





  async metrics(
    ip,
  ) {


    const result =
      await request(
        `/api/metrics/${encodeURIComponent(ip)}`,
      )


    return result.metrics || result

  },





  async lte(
    ip,
  ) {


    const result =
      await request(
        `/api/lte/${encodeURIComponent(ip)}`,
      )


    return result.lte || result

  },





  routeros(
    ip,
  ) {

    return request(
      `/api/v1/devices/${encodeURIComponent(ip)}/routeros`,
    )

  },





  traffic(
    ip,
  ) {


    return request(
      `/api/v1/devices/${encodeURIComponent(ip)}/traffic`,
    )

  },







  trafficHistory(
    ip,
    {
      interfaceName = '',
      minutes = 15,
      window = 10,
    } = {},
  ) {


    const searchParams =
      new URLSearchParams(
        {
          minutes:
            String(minutes),

          window:
            String(window),
        },
      )



    if (interfaceName) {

      searchParams.set(
        'interface',
        interfaceName,
      )

    }



    return request(
      `/api/v1/devices/${encodeURIComponent(ip)}/traffic/history?${searchParams.toString()}`,
    )

  },







  interfaces(
    ip,
    minutes = 15,
  ) {


    const searchParams =
      new URLSearchParams(
        {
          minutes:
            String(minutes),
        },
      )



    return request(
      `/api/v1/devices/${encodeURIComponent(ip)}/interfaces?${searchParams.toString()}`,
    )

  },







  // =====================================================
  // H23.4.5.5.12.19
  // Notification Audit Dashboard Integration
  // =====================================================



  notificationAuditStats() {


    return request(
      '/api/v1/notifications/audit/stats',
    )

  },





  notificationAuditTimeline(
    period = 'hour',
  ) {


    return request(
      `/api/v1/notifications/audit/timeline?period=${period}`,
    )

  },





  notificationAuditSearch(
    params = {},
  ) {


    const searchParams =
      new URLSearchParams()



    Object.entries(
      params,
    ).forEach(
      ([key,value]) => {


        if (
          value !== undefined &&
          value !== null &&
          value !== ''
        ) {


          searchParams.set(
            key,
            value,
          )


        }


      },
    )



    return request(
      `/api/v1/notifications/audit/search?${searchParams.toString()}`,
    )

  },








  // =====================================================
  // H23.4.5.5.12.20.4
  // Notification Audit Intelligence
  // =====================================================



  notificationAuditIntelligence() {


    return request(
      '/api/v1/notifications/audit/intelligence',
    )

  },








  // =====================================================
  // H23.4.5.5.12.21.4
  // Notification Audit Decision Engine
  // =====================================================



  notificationAuditDecision() {


    return request(
      '/api/v1/notifications/audit/decision',
    )

  },





}







export {
  API_BASE_URL,
}
