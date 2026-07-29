import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowRight,
  Cpu,
  MemoryStick,
  RadioTower,
  Router,
  Signal,
  Thermometer,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import StatCard from '../components/dashboard/StatCard'
import { api } from '../services/api'
import {
  formatTemperature,
  formatUptime,
} from '../utils/formatters'

export default function DeviceDetails() {
  const { ip } = useParams()
  const navigate = useNavigate()
  const decodedIp = decodeURIComponent(ip)

  const [device, setDevice] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [lte, setLte] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  async function loadDevice(isRefresh = false) {
    try {
      setError('')
      isRefresh ? setRefreshing(true) : setLoading(true)

      const [devices, metricData, lteResult] =
        await Promise.all([
          api.devices(),
          api.metrics(decodedIp),
          api.lte(decodedIp).catch(() => null),
        ])

      setDevice(
        devices.find((item) => item.ip === decodedIp) || {
          name: decodedIp,
          ip: decodedIp,
        },
      )
      setMetrics(metricData)
      setLte(lteResult)
      setLastUpdated(new Date())
    } catch (requestError) {
      console.error(requestError)
      setError('تعذر تحميل تفاصيل الجهاز.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadDevice()
  }, [decodedIp])

  return (
    <>
      <Header
        title={device?.name || 'تفاصيل الجهاز'}
        subtitle={`مراقبة الجهاز ${decodedIp}`}
        onRefresh={() => loadDevice(true)}
        refreshing={refreshing}
        lastUpdated={lastUpdated}
      />

      <button
        type="button"
        className="back-button"
        onClick={() => navigate('/')}
      >
        <ArrowRight size={17} />
        العودة إلى لوحة التحكم
      </button>

      {error && <div className="error-banner">{error}</div>}

      <section className="stats-grid device-details-stats">
        <StatCard
          title="الحالة"
          value={
            device?.status === 'online' ? 'متصل' : 'غير متصل'
          }
          description={decodedIp}
          icon={Router}
          tone={device?.status === 'online' ? 'green' : 'red'}
        />

        <StatCard
          title="استخدام CPU"
          value={`${metrics?.cpu_usage ?? '--'}%`}
          description="CPU Load"
          icon={Cpu}
        />

        <StatCard
          title="استخدام الذاكرة"
          value={`${metrics?.memory_usage ?? '--'}%`}
          description="Memory Usage"
          icon={MemoryStick}
        />

        <StatCard
          title="درجة الحرارة"
          value={formatTemperature(metrics?.temperature)}
          description="System Temperature"
          icon={Thermometer}
        />

        <StatCard
          title="زمن التشغيل"
          value={formatUptime(metrics?.uptime_seconds)}
          description="Device Uptime"
          icon={Activity}
          tone="purple"
        />

        <StatCard
          title="المشغل الخلوي"
          value={lte?.operator || 'غير متوفر'}
          description={lte?.technology || 'LTE / 5G'}
          icon={RadioTower}
          tone="purple"
        />

        <StatCard
          title="جودة الإشارة"
          value={
            lte?.rsrp !== undefined
              ? `${lte.rsrp} dBm`
              : 'غير متوفر'
          }
          description={`SINR: ${lte?.sinr ?? '--'}`}
          icon={Signal}
          tone="green"
        />
      </section>

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Device Information</p>
              <h3>معلومات الجهاز</h3>
            </div>

            <Router size={22} />
          </div>

          <div className="details-list">
            <div>
              <span>اسم الجهاز</span>
              <strong>{device?.name || '--'}</strong>
            </div>
            <div>
              <span>عنوان IP</span>
              <strong>{decodedIp}</strong>
            </div>
            <div>
              <span>الموقع</span>
              <strong>{device?.site || '--'}</strong>
            </div>
            <div>
              <span>النوع</span>
              <strong>{device?.type || '--'}</strong>
            </div>
            <div>
              <span>الحالة</span>
              <strong>{device?.status || '--'}</strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">LTE / 5G Information</p>
              <h3>الاتصال الخلوي</h3>
            </div>

            <RadioTower size={22} />
          </div>

          <div className="details-list">
            <div>
              <span>المشغل</span>
              <strong>{lte?.operator || '--'}</strong>
            </div>
            <div>
              <span>التقنية</span>
              <strong>{lte?.technology || '--'}</strong>
            </div>
            <div>
              <span>الباند</span>
              <strong>{lte?.band || '--'}</strong>
            </div>
            <div>
              <span>Cell ID</span>
              <strong>{lte?.cell_id || '--'}</strong>
            </div>
            <div>
              <span>PCI</span>
              <strong>{lte?.pci ?? '--'}</strong>
            </div>
            <div>
              <span>RSRP</span>
              <strong>{lte?.rsrp ?? '--'}</strong>
            </div>
            <div>
              <span>RSRQ</span>
              <strong>{lte?.rsrq ?? '--'}</strong>
            </div>
            <div>
              <span>SINR</span>
              <strong>{lte?.sinr ?? '--'}</strong>
            </div>
          </div>
        </article>
      </section>

      {loading && (
        <div className="loading-overlay">
          <Activity className="spin" size={34} />
          <span>جاري تحميل تفاصيل الجهاز...</span>
        </div>
      )}
    </>
  )
}
