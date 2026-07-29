import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Cpu,
  MemoryStick,
  RadioTower,
  Router,
  Server,
  Wifi,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/layout/Header'
import RecentEvents from '../components/dashboard/RecentEvents'
import StatCard from '../components/dashboard/StatCard'
import TopCpuDevices from '../components/dashboard/TopCpuDevices'
import TrafficChart from '../components/dashboard/TrafficChart'
import { api } from '../services/api'
import { formatPercentage } from '../utils/formatters'

const EVENT_STORAGE_KEY = 'ss4ts-noc-events'
const TRAFFIC_STORAGE_KEY = 'ss4ts-noc-traffic'

function readStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key))
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

export default function Dashboard() {
  const navigate = useNavigate()

  const [devices, setDevices] = useState([])
  const [metrics, setMetrics] = useState({})
  const [trafficHistory, setTrafficHistory] = useState(() =>
    readStoredArray(TRAFFIC_STORAGE_KEY).slice(-30),
  )
  const [events, setEvents] = useState(() =>
    readStoredArray(EVENT_STORAGE_KEY).slice(0, 50),
  )
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const previousStatusRef = useRef({})

  function addEvents(newEvents) {
    if (newEvents.length === 0) return

    setEvents((current) => {
      const next = [...newEvents, ...current].slice(0, 50)
      localStorage.setItem(EVENT_STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  function detectEvents(deviceList, metricMap) {
    const detected = []
    const now = new Date()
    const readableTime = now.toLocaleTimeString('ar-SA')

    deviceList.forEach((device) => {
      const previousStatus = previousStatusRef.current[device.ip]
      const currentStatus = device.status
      const deviceMetrics = metricMap[device.ip] || {}

      if (previousStatus && previousStatus !== currentStatus) {
        detected.push({
          id: `${Date.now()}-${device.ip}-status`,
          type: currentStatus === 'online' ? 'recovered' : 'offline',
          title:
            currentStatus === 'online'
              ? 'تمت استعادة الجهاز'
              : 'الجهاز متوقف',
          message: `${device.name} — ${device.ip}`,
          time: readableTime,
        })
      }

      if (Number(deviceMetrics.cpu_usage) >= 90) {
        detected.push({
          id: `${Date.now()}-${device.ip}-cpu`,
          type: 'cpu',
          title: 'ارتفاع استخدام المعالج',
          message: `${device.name}: CPU ${deviceMetrics.cpu_usage}%`,
          time: readableTime,
        })
      }

      if (Number(deviceMetrics.temperature) >= 70) {
        detected.push({
          id: `${Date.now()}-${device.ip}-temperature`,
          type: 'temperature',
          title: 'ارتفاع درجة الحرارة',
          message: `${device.name}: ${deviceMetrics.temperature}°C`,
          time: readableTime,
        })
      }

      previousStatusRef.current[device.ip] = currentStatus
    })

    addEvents(detected)
  }

  function appendTraffic(metricMap) {
    const values = Object.values(metricMap)

    const rxBps = values.reduce(
      (total, item) => total + Number(item.rx_bps || 0),
      0,
    )

    const txBps = values.reduce(
      (total, item) => total + Number(item.tx_bps || 0),
      0,
    )

    const point = {
      timestamp: Date.now(),
      time: new Date().toLocaleTimeString('ar-SA', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
      rx_bps: rxBps,
      tx_bps: txBps,
    }

    setTrafficHistory((current) => {
      const last = current.at(-1)

      if (
        last &&
        last.rx_bps === point.rx_bps &&
        last.tx_bps === point.tx_bps &&
        Date.now() - last.timestamp < 10000
      ) {
        return current
      }

      const next = [...current, point].slice(-30)
      localStorage.setItem(TRAFFIC_STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  async function loadData(isRefresh = false) {
    try {
      setError('')
      isRefresh ? setRefreshing(true) : setLoading(true)

      const deviceList = await api.devices()

      const results = await Promise.allSettled(
        deviceList.map(async (device) => {
          const data = await api.metrics(device.ip)
          return [device.ip, data]
        }),
      )

      const metricMap = {}

      results.forEach((result) => {
        if (result.status === 'fulfilled') {
          const [ip, data] = result.value
          metricMap[ip] = data
        }
      })

      setDevices(deviceList)
      setMetrics(metricMap)
      setLastUpdated(new Date())

      appendTraffic(metricMap)
      detectEvents(deviceList, metricMap)
    } catch (requestError) {
      console.error(requestError)
      setError(
        requestError.message ||
          'تعذر تحميل بيانات لوحة التحكم من خادم API.',
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()

    const interval = setInterval(() => {
      loadData(true)
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  const summary = useMemo(() => {
    const online = devices.filter(
      (device) => device.status === 'online',
    ).length

    const offline = devices.filter(
      (device) => device.status !== 'online',
    ).length

    const values = Object.values(metrics)

    const averageCpu =
      values.length > 0
        ? Math.round(
            values.reduce(
              (total, item) =>
                total + Number(item.cpu_usage || 0),
              0,
            ) / values.length,
          )
        : 0

    const averageMemory =
      values.length > 0
        ? Math.round(
            values.reduce(
              (total, item) =>
                total + Number(item.memory_usage || 0),
              0,
            ) / values.length,
          )
        : 0

    const health =
      devices.length > 0
        ? Math.round((online / devices.length) * 100)
        : 0

    const criticalEvents = events.filter((event) =>
      ['offline', 'cpu', 'temperature'].includes(event.type),
    ).length

    return {
      total: devices.length,
      online,
      offline,
      averageCpu,
      averageMemory,
      health,
      criticalEvents,
    }
  }, [devices, metrics, events])

  const filteredDevices = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) return devices

    return devices.filter((device) =>
      [
        device.name,
        device.ip,
        device.site,
        device.type,
        device.status,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(query),
        ),
    )
  }, [devices, search])

  const topCpuDevices = useMemo(
    () =>
      devices
        .map((device) => ({
          ...device,
          cpu: Number(metrics[device.ip]?.cpu_usage || 0),
        }))
        .sort((first, second) => second.cpu - first.cpu),
    [devices, metrics],
  )

  return (
    <>
      <Header
        title="لوحة التحكم"
        subtitle="ملخص شامل لحالة الشبكة والأجهزة والخدمات"
        onRefresh={() => loadData(true)}
        refreshing={refreshing}
        searchValue={search}
        onSearchChange={setSearch}
        lastUpdated={lastUpdated}
      />

      {error && <div className="error-banner">{error}</div>}

      <section className="stats-grid">
        <StatCard
          title="إجمالي الأجهزة"
          value={summary.total}
          description="الأجهزة المسجلة"
          icon={Router}
        />

        <StatCard
          title="الأجهزة المتصلة"
          value={summary.online}
          description="تعمل بصورة طبيعية"
          icon={Wifi}
          tone="green"
        />

        <StatCard
          title="الأجهزة المتوقفة"
          value={summary.offline}
          description="تحتاج إلى مراجعة"
          icon={AlertTriangle}
          tone={summary.offline > 0 ? 'red' : 'green'}
        />

        <StatCard
          title="صحة الشبكة"
          value={`${summary.health}%`}
          description="مؤشر الحالة العام"
          icon={Activity}
          tone="purple"
        />

        <StatCard
          title="متوسط CPU"
          value={formatPercentage(summary.averageCpu)}
          description="متوسط جميع الأجهزة"
          icon={Cpu}
        />

        <StatCard
          title="متوسط الذاكرة"
          value={formatPercentage(summary.averageMemory)}
          description="متوسط جميع الأجهزة"
          icon={MemoryStick}
        />

        <StatCard
          title="أجهزة LTE و5G"
          value={devices.length}
          description="الأجهزة الخلوية المسجلة"
          icon={RadioTower}
          tone="purple"
        />

        <StatCard
          title="خدمات المنصة"
          value="4/4"
          description="FastAPI / InfluxDB / Grafana / Telegraf"
          icon={Server}
          tone="green"
        />
      </section>

      <section className="dashboard-grid">
        <article className="panel wide-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Network Health</p>
              <h3>صحة الشبكة</h3>
            </div>

            <strong className="health-value">
              {summary.health}%
            </strong>
          </div>

          <div className="health-track">
            <div
              className="health-progress"
              style={{ width: `${summary.health}%` }}
            />
          </div>

          <div className="health-footer">
            <span>{summary.online} جهاز متصل</span>
            <span>{summary.offline} جهاز متوقف</span>
          </div>
        </article>

        <TrafficChart data={trafficHistory} />

        <article className="panel devices-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Devices</p>
              <h3>حالة الأجهزة</h3>
            </div>

            <span className="result-count">
              {filteredDevices.length} نتيجة
            </span>
          </div>

          <div className="device-list">
            {filteredDevices.map((device) => (
              <button
                type="button"
                className="device-list-item clickable"
                key={device.ip}
                onClick={() =>
                  navigate(`/devices/${encodeURIComponent(device.ip)}`)
                }
              >
                <span
                  className={`status-dot ${
                    device.status === 'online'
                      ? 'online'
                      : 'offline'
                  }`}
                />

                <div>
                  <strong>{device.name}</strong>
                  <span>
                    {device.site} — {device.ip}
                  </span>
                </div>

                <div className="device-list-metrics">
                  <span>
                    CPU: {metrics[device.ip]?.cpu_usage ?? '--'}%
                  </span>
                  <span>
                    RAM: {metrics[device.ip]?.memory_usage ?? '--'}%
                  </span>
                </div>
              </button>
            ))}

            {!loading && filteredDevices.length === 0 && (
              <div className="events-empty">
                <Router size={35} />
                <strong>لا توجد نتائج</strong>
                <span>جرّب اسمًا أو IP أو موقعًا مختلفًا.</span>
              </div>
            )}
          </div>
        </article>

        <TopCpuDevices devices={topCpuDevices} />

        <RecentEvents events={events} />
      </section>

      {loading && (
        <div className="loading-overlay">
          <Activity className="spin" size={34} />
          <span>جاري تحميل بيانات الشبكة...</span>
        </div>
      )}
    </>
  )
}
