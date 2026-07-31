import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Cpu,
  MemoryStick,
  Network,
  RadioTower,
  Router,
  Signal,
  Thermometer,
} from 'lucide-react'

import {
  useNavigate,
  useParams,
} from 'react-router-dom'

import StatCard from '../components/dashboard/StatCard'
import DeviceHealthCenter from '../components/device/DeviceHealthCenter'
import DecisionIntelligenceCenter from '../components/device/DecisionIntelligenceCenter'
import InterfacesTable from '../components/device/InterfacesTable'
import LiveTrafficChart from '../components/device/LiveTrafficChart'
import Header from '../components/layout/Header'

import { api } from '../services/api'

import {
  formatBitrate,
  formatTemperature,
  formatUptime,
} from '../utils/formatters'


function displayValue(value, suffix = '') {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return 'غير متوفر'
  }

  return `${value}${suffix}`
}


function formatMemory(bytes) {
  const numericValue = Number(bytes)

  if (
    !Number.isFinite(numericValue) ||
    numericValue <= 0
  ) {
    return 'غير متوفر'
  }

  return `${(
    numericValue /
    1024 /
    1024
  ).toFixed(1)} MB`
}


export default function DeviceDetails() {
  const { ip } = useParams()
  const navigate = useNavigate()

  const decodedIp = decodeURIComponent(ip || '')

  const [device, setDevice] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [lte, setLte] = useState(null)
  const [routeros, setRouteros] = useState(null)
  const [traffic, setTraffic] = useState(null)

  const [
    selectedInterface,
    setSelectedInterface,
  ] = useState('')

  const [interfacesSnapshot, setInterfacesSnapshot] =
    useState({
      interfaces: [],
      summary: null,
      loading: true,
      error: '',
      lastUpdated: null,
    })

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] =
    useState(false)

  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] =
    useState(null)

  const loadDevice = useCallback(
    async (isRefresh = false) => {
      try {
        setError('')

        if (isRefresh) {
          setRefreshing(true)
        } else {
          setLoading(true)
        }

        const [
          devices,
          metricData,
          lteResult,
          routerosResult,
          trafficResult,
        ] = await Promise.all([
          api.devices(),

          api
            .metrics(decodedIp)
            .catch((requestError) => {
              console.error(
                'Metrics API:',
                requestError,
              )

              return null
            }),

          api
            .lte(decodedIp)
            .catch((requestError) => {
              console.error(
                'LTE API:',
                requestError,
              )

              return null
            }),

          api
            .routeros(decodedIp)
            .catch((requestError) => {
              console.error(
                'RouterOS API:',
                requestError,
              )

              return null
            }),

          api
            .traffic(decodedIp)
            .catch((requestError) => {
              console.error(
                'Traffic API:',
                requestError,
              )

              return null
            }),
        ])

        const currentDevice =
          devices.find(
            (item) => item.ip === decodedIp,
          ) || {
            name:
              routerosResult?.identity ||
              decodedIp,
            ip: decodedIp,
            status: 'unknown',
            site: 'غير محدد',
          }

        setDevice(currentDevice)
        setMetrics(metricData)
        setLte(lteResult)
        setRouteros(routerosResult)
        setTraffic(trafficResult)
        setLastUpdated(new Date())
      } catch (requestError) {
        console.error(
          'Device details request failed:',
          requestError,
        )

        setError(
          'تعذر تحميل تفاصيل الجهاز.',
        )
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [decodedIp],
  )

  useEffect(() => {
    loadDevice(false)

    const intervalId =
      globalThis.setInterval(() => {
        loadDevice(true)
      }, 15000)

    return () => {
      globalThis.clearInterval(intervalId)
    }
  }, [loadDevice])

  useEffect(() => {
    const apiSelectedInterface =
      traffic?.selected_interface

    if (
      apiSelectedInterface &&
      !selectedInterface
    ) {
      setSelectedInterface(
        apiSelectedInterface,
      )
    }
  }, [
    selectedInterface,
    traffic?.selected_interface,
  ])

  const cpuUsage =
    routeros?.cpu_usage ??
    metrics?.cpu_usage ??
    null

  const memoryUsage =
    routeros?.memory_usage ??
    metrics?.memory_usage ??
    null

  const temperature =
    routeros?.temperature ??
    metrics?.temperature ??
    null

  const uptime =
    routeros?.uptime ??
    metrics?.uptime_seconds ??
    null

  const rxBps =
    traffic?.rx_bps ??
    metrics?.rx_bps ??
    null

  const txBps =
    traffic?.tx_bps ??
    metrics?.tx_bps ??
    null

  const isOnline =
    device?.status === 'online'

  return (
    <>
      <Header
        title={
          routeros?.identity ||
          device?.name ||
          'تفاصيل الجهاز'
        }
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

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {loading && !device ? (
        <div className="panel loading-panel">
          <Activity
            size={26}
            className="is-spinning"
          />

          <span>
            جارٍ تحميل تفاصيل الجهاز...
          </span>
        </div>
      ) : (
        <>
          <section className="stats-grid device-details-stats">
            <StatCard
              title="الحالة"
              value={
                isOnline
                  ? 'متصل'
                  : 'غير متصل'
              }
              description={decodedIp}
              icon={Router}
              tone={
                isOnline
                  ? 'green'
                  : 'red'
              }
            />

            <StatCard
              title="استخدام CPU"
              value={
                cpuUsage === null
                  ? 'غير متوفر'
                  : `${cpuUsage}%`
              }
              description={
                routeros?.cpu ||
                'CPU Load'
              }
              icon={Cpu}
              tone={
                Number(cpuUsage) >= 90
                  ? 'red'
                  : Number(cpuUsage) >= 70
                    ? 'orange'
                    : undefined
              }
            />

            <StatCard
              title="استخدام الذاكرة"
              value={
                memoryUsage === null
                  ? 'غير متوفر'
                  : `${memoryUsage}%`
              }
              description="Memory Usage"
              icon={MemoryStick}
              tone={
                Number(memoryUsage) >= 90
                  ? 'red'
                  : Number(memoryUsage) >= 75
                    ? 'orange'
                    : undefined
              }
            />

            <StatCard
              title="درجة الحرارة"
              value={
                temperature === null
                  ? 'غير مدعوم'
                  : formatTemperature(
                      temperature,
                    )
              }
              description="System Temperature"
              icon={Thermometer}
              tone={
                Number(temperature) >= 75
                  ? 'red'
                  : Number(temperature) >= 60
                    ? 'orange'
                    : undefined
              }
            />

            <StatCard
              title="زمن التشغيل"
              value={formatUptime(uptime)}
              description="Device Uptime"
              icon={Activity}
              tone="purple"
            />

            <StatCard
              title="Download"
              value={formatBitrate(rxBps)}
              description={
                traffic?.selected_interface ||
                'Live RX Traffic'
              }
              icon={ArrowDown}
              tone="green"
            />

            <StatCard
              title="Upload"
              value={formatBitrate(txBps)}
              description={
                traffic?.selected_interface ||
                'Live TX Traffic'
              }
              icon={ArrowUp}
              tone="purple"
            />

            <StatCard
              title="المشغل الخلوي"
              value={
                lte?.operator ||
                'غير متوفر'
              }
              description={
                lte?.technology ||
                'LTE / 5G'
              }
              icon={RadioTower}
              tone="purple"
            />

            <StatCard
              title="جودة الإشارة"
              value={
                lte?.rsrp !== null &&
                lte?.rsrp !== undefined
                  ? `${lte.rsrp} dBm`
                  : 'غير متوفر'
              }
              description={`SINR: ${
                lte?.sinr ?? '--'
              }`}
              icon={Signal}
              tone="green"
            />
          </section>

          <DeviceHealthCenter
            isOnline={isOnline}
            cpuUsage={cpuUsage}
            memoryUsage={memoryUsage}
            interfaces={
              interfacesSnapshot.interfaces
            }
          />

          <DecisionIntelligenceCenter
            ip={decodedIp}
            selectedInterface={
              selectedInterface
            }
            minutes={15}
            windowSeconds={10}
            refreshInterval={30000}
          />

          <LiveTrafficChart
            ip={decodedIp}
            interfaces={
              traffic?.interfaces || []
            }
            defaultInterface={
              traffic?.selected_interface ||
              ''
            }
            selectedInterface={
              selectedInterface
            }
            onSelectInterface={
              setSelectedInterface
            }
          />

          <InterfacesTable
            ip={decodedIp}
            selectedInterface={
              selectedInterface
            }
            onSelectInterface={
              setSelectedInterface
            }
            onInterfacesData={
              setInterfacesSnapshot
            }
            refreshInterval={15000}
          />

          <section className="dashboard-grid">
            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">
                    Device Information
                  </p>

                  <h3>
                    معلومات الجهاز
                  </h3>
                </div>

                <Router size={22} />
              </div>

              <div className="details-list">
                <div>
                  <span>
                    اسم الجهاز
                  </span>

                  <strong>
                    {routeros?.identity ||
                      device?.name ||
                      '--'}
                  </strong>
                </div>

                <div>
                  <span>
                    عنوان IP
                  </span>

                  <strong>
                    {decodedIp}
                  </strong>
                </div>

                <div>
                  <span>
                    الموديل
                  </span>

                  <strong>
                    {routeros?.board_name ||
                      'غير متوفر'}
                  </strong>
                </div>

                <div>
                  <span>
                    إصدار RouterOS
                  </span>

                  <strong>
                    {routeros?.version ||
                      'غير متوفر'}
                  </strong>
                </div>

                <div>
                  <span>
                    المنصة
                  </span>

                  <strong>
                    {routeros?.platform ||
                      device?.type ||
                      '--'}
                  </strong>
                </div>

                <div>
                  <span>
                    المعمارية
                  </span>

                  <strong>
                    {routeros?.architecture ||
                      'غير متوفر'}
                  </strong>
                </div>

                <div>
                  <span>
                    الموقع
                  </span>

                  <strong>
                    {device?.site ||
                      '--'}
                  </strong>
                </div>

                <div>
                  <span>
                    الحالة
                  </span>

                  <strong>
                    {isOnline
                      ? 'متصل'
                      : 'غير متصل'}
                  </strong>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">
                    Live Traffic
                  </p>

                  <h3>
                    ملخص حركة الشبكة
                  </h3>
                </div>

                <Network size={22} />
              </div>

              <div className="details-list">
                <div>
                  <span>
                    المنفذ المختار
                  </span>

                  <strong>
                    {selectedInterface ||
                      traffic?.selected_interface ||
                      'غير متوفر'}
                  </strong>
                </div>

                <div>
                  <span>
                    Download
                  </span>

                  <strong>
                    {formatBitrate(rxBps)}
                  </strong>
                </div>

                <div>
                  <span>
                    Upload
                  </span>

                  <strong>
                    {formatBitrate(txBps)}
                  </strong>
                </div>

                <div>
                  <span>
                    إجمالي الحركة
                  </span>

                  <strong>
                    {formatBitrate(
                      traffic?.total_bps,
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    عدد المنافذ
                  </span>

                  <strong>
                    {traffic?.interfaces
                      ?.length ?? 0}
                  </strong>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">
                    System Resources
                  </p>

                  <h3>
                    موارد النظام
                  </h3>
                </div>

                <Cpu size={22} />
              </div>

              <div className="details-list">
                <div>
                  <span>
                    نوع المعالج
                  </span>

                  <strong>
                    {routeros?.cpu ||
                      'غير متوفر'}
                  </strong>
                </div>

                <div>
                  <span>
                    عدد الأنوية
                  </span>

                  <strong>
                    {displayValue(
                      routeros?.cpu_count,
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    تردد المعالج
                  </span>

                  <strong>
                    {displayValue(
                      routeros
                        ?.cpu_frequency_mhz,
                      ' MHz',
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    استخدام المعالج
                  </span>

                  <strong>
                    {displayValue(
                      cpuUsage,
                      '%',
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    الذاكرة الكلية
                  </span>

                  <strong>
                    {formatMemory(
                      routeros
                        ?.total_memory_bytes,
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    الذاكرة الحرة
                  </span>

                  <strong>
                    {formatMemory(
                      routeros
                        ?.free_memory_bytes,
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    استخدام الذاكرة
                  </span>

                  <strong>
                    {displayValue(
                      memoryUsage,
                      '%',
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    زمن التشغيل
                  </span>

                  <strong>
                    {formatUptime(uptime)}
                  </strong>
                </div>
              </div>
            </article>
          </section>
        </>
      )}
    </>
  )
}
