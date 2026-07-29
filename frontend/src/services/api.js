const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://192.168.45.196:8000'

async function request(endpoint, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`API error: HTTP ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('انتهت مهلة الاتصال بخادم API')
    }

    throw error
  } finally {
    clearTimeout(timeout)
  }
}

function normalizeDevice(device) {
  return {
    ...device,
    ip: device.ip || device.ip_address,
    name: device.name || device.identity || 'MikroTik Router',
    type:
      device.type ||
      device.device_type ||
      device.model ||
      'MikroTik RouterOS',
    site: device.site || 'غير محدد',
    status: device.status || 'unknown',
  }
}

export const api = {
  health() {
    return request('/api/health')
  },

  systemStatus() {
    return request('/api/system/status')
  },

  async devices() {
    const result = await request('/api/devices')
    const devices = Array.isArray(result) ? result : result.devices || []

    return devices.map(normalizeDevice)
  },

  device(ip) {
    return request(`/api/devices/${encodeURIComponent(ip)}`)
  },

  async metrics(ip) {
    const result = await request(`/api/metrics/${encodeURIComponent(ip)}`)
    return result.metrics || result
  },

  async lte(ip) {
    const result = await request(`/api/lte/${encodeURIComponent(ip)}`)
    return result.lte || result
  },
}

export { API_BASE_URL }
