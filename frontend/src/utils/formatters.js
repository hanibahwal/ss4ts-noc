export function formatUptime(value) {
  if (value === null || value === undefined) {
    return 'غير متوفر'
  }

  if (typeof value === 'string') {
    return value
  }

  const seconds = Number(value)

  if (!Number.isFinite(seconds)) {
    return 'غير متوفر'
  }

  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  return `${days} يوم ${hours} ساعة ${minutes} دقيقة`
}

export function formatPercentage(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${number}%` : '--'
}

export function formatTemperature(value) {
  if (value === null || value === undefined || value === '') {
    return 'غير مدعوم'
  }

  const number = Number(value)
  return Number.isFinite(number) ? `${number}°C` : 'غير مدعوم'
}

export function formatBitrate(value) {
  const number = Number(value)

  if (!Number.isFinite(number)) {
    return '--'
  }

  if (number >= 1_000_000_000) {
    return `${(number / 1_000_000_000).toFixed(2)} Gbps`
  }

  if (number >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(2)} Mbps`
  }

  if (number >= 1_000) {
    return `${(number / 1_000).toFixed(2)} Kbps`
  }

  return `${number} bps`
}

export function getSignalQuality(rsrp) {
  const value = Number(rsrp)

  if (!Number.isFinite(value)) {
    return {
      label: 'غير متوفر',
      level: 'unknown',
      percentage: 0,
    }
  }

  if (value >= -80) {
    return {
      label: 'ممتاز',
      level: 'excellent',
      percentage: 100,
    }
  }

  if (value >= -90) {
    return {
      label: 'جيد جدًا',
      level: 'good',
      percentage: 80,
    }
  }

  if (value >= -100) {
    return {
      label: 'متوسط',
      level: 'medium',
      percentage: 55,
    }
  }

  if (value >= -110) {
    return {
      label: 'ضعيف',
      level: 'weak',
      percentage: 30,
    }
  }

  return {
    label: 'ضعيف جدًا',
    level: 'critical',
    percentage: 10,
  }
}
