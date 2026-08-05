import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  Gauge,
  Network,
  RadioTower,
  RefreshCw,
  Router,
  ShieldAlert,
  Signal,
  Wifi,
  XCircle,
} from 'lucide-react'

import useNetworkIntelligence from '../../hooks/useNetworkIntelligence'

import {
  formatBitrate,
} from '../../utils/formatters'

import {
  SSGauge,
  SSProgress,
  SSStatusChip,
} from '../ui'

import './NetworkIntelligenceCenter.css'


const STATUS_PRESENTATION = {
  excellent: {
    label: 'ممتاز',
    tone: 'success',
  },

  healthy: {
    label: 'سليم',
    tone: 'success',
  },

  degraded: {
    label: 'متدهور',
    tone: 'warning',
  },

  critical: {
    label: 'حرج',
    tone: 'danger',
  },

  unavailable: {
    label: 'غير متاح',
    tone: 'neutral',
  },

  unknown: {
    label: 'غير معروف',
    tone: 'neutral',
  },
}


const SEVERITY_PRESENTATION = {
  critical: {
    label: 'حرج',
    icon: ShieldAlert,
    className: 'critical',
  },

  high: {
    label: 'مرتفع',
    icon: AlertTriangle,
    className: 'high',
  },

  warning: {
    label: 'تحذير',
    icon: AlertTriangle,
    className: 'warning',
  },

  info: {
    label: 'معلومة',
    icon: AlertCircle,
    className: 'info',
  },
}


function formatNumber(
  value,
  suffix = '',
  digits = 2,
) {
  const numericValue =
    Number(value)

  if (
    !Number.isFinite(
      numericValue,
    )
  ) {
    return 'غير متوفر'
  }

  return (
    new Intl.NumberFormat(
      'ar-SA',
      {
        maximumFractionDigits:
          digits,
      },
    ).format(numericValue) +
    suffix
  )
}


function formatDate(value) {
  if (!value) {
    return 'لم يتم التحديث'
  }

  const date =
    value instanceof Date
      ? value
      : new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return 'غير معروف'
  }

  return new Intl.DateTimeFormat(
    'ar-SA',
    {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    },
  ).format(date)
}


function MetricCard({
  icon: Icon,
  label,
  value,
  description,
}) {
  return (
    <div className="network-intelligence-metric">
      <span className="network-intelligence-metric__icon">
        <Icon size={18} />
      </span>

      <div>
        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

        {description ? (
          <small>
            {description}
          </small>
        ) : null}
      </div>
    </div>
  )
}


function SourceCard({
  source,
}) {
  const available =
    source.available

  const Icon =
    available
      ? CheckCircle2
      : XCircle

  return (
    <div
      className={
        `network-intelligence-source ` +
        (
          available
            ? 'available'
            : 'unavailable'
        )
      }
      title={
        source.error ||
        source.status
      }
    >
      <Icon size={16} />

      <span>
        {source.name}
      </span>

      <strong>
        {available
          ? 'متاح'
          : 'غير متاح'}
      </strong>
    </div>
  )
}


function FindingCard({
  finding,
}) {
  const presentation =
    SEVERITY_PRESENTATION[
      finding.severity
    ] ||
    SEVERITY_PRESENTATION.info

  const Icon =
    presentation.icon

  return (
    <article
      className={
        `network-intelligence-finding ` +
        presentation.className
      }
    >
      <span className="network-intelligence-finding__icon">
        <Icon size={18} />
      </span>

      <div>
        <header>
          <strong>
            {finding.title}
          </strong>

          <span>
            {presentation.label}
          </span>
        </header>

        <p>
          {finding.message}
        </p>

        {finding.recommendation ? (
          <small>
            {finding.recommendation}
          </small>
        ) : null}
      </div>
    </article>
  )
}


export default function NetworkIntelligenceCenter({
  ip,
  refreshInterval = 30000,
}) {
  const {
    data,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh,
  } = useNetworkIntelligence(
    ip,
    {
      includeHistory: true,
      historyMinutes: 15,
      historyWindowSeconds: 10,
      refreshInterval,
    },
  )

  const status =
    data?.status ||
    'unknown'

  const presentation =
    STATUS_PRESENTATION[status] ||
    STATUS_PRESENTATION.unknown

  const healthTone =
    status === 'critical'
      ? 'danger'
      : status === 'degraded'
        ? 'warning'
        : status === 'unavailable'
          ? 'neutral'
          : 'success'

  if (loading && !data) {
    return (
      <article className="panel network-intelligence-panel network-intelligence-loading">
        <Activity
          className="is-spinning"
          size={28}
        />

        <span>
          جارٍ تحميل Network Intelligence...
        </span>
      </article>
    )
  }

  return (
    <article className="panel network-intelligence-panel">
      <header className="network-intelligence-header">
        <div className="network-intelligence-title">
          <span className="network-intelligence-title__icon">
            <BrainCircuit size={24} />
          </span>

          <div>
            <p className="eyebrow">
              Network Intelligence Engine
            </p>

            <h3>
              مركز ذكاء الشبكة
            </h3>

            <span>
              تحليل موحّد للجهاز وحركة الشبكة والاتصال وLTE
            </span>
          </div>
        </div>

        <div className="network-intelligence-header__actions">
          <SSStatusChip
            status={status}
            label={presentation.label}
            tone={presentation.tone}
            showIcon
          />

          <button
            type="button"
            className="network-intelligence-refresh"
            onClick={refresh}
            disabled={refreshing}
          >
            <RefreshCw
              size={17}
              className={
                refreshing
                  ? 'is-spinning'
                  : ''
              }
            />

            تحديث
          </button>
        </div>
      </header>

      {error ? (
        <div className="network-intelligence-error">
          <AlertTriangle size={18} />
          {error}
        </div>
      ) : null}

      {data ? (
        <>
          <section className="network-intelligence-overview">
            <div className="network-intelligence-gauges">
              <SSGauge
                value={data.healthScore}
                min={0}
                max={100}
                valueSuffix="/100"
                label="Health Score"
                description="درجة صحة الشبكة"
                tone={healthTone}
                size="lg"
                thickness={9}
                animated
              />

              <SSGauge
                value={data.confidencePercent}
                min={0}
                max={100}
                valueSuffix="%"
                label="Confidence"
                description="موثوقية التحليل"
                tone={
                  data.confidencePercent >= 85
                    ? 'success'
                    : data.confidencePercent >= 65
                      ? 'primary'
                      : data.confidencePercent >= 40
                        ? 'warning'
                        : 'danger'
                }
                size="lg"
                thickness={9}
                animated
              />
            </div>

            <div className="network-intelligence-summary">
              <MetricCard
                icon={Database}
                label="المصادر المتاحة"
                value={
                  `${data.summary.availableSources}` +
                  ` / ${data.summary.totalSources}`
                }
                description={
                  `${data.summary.unavailableSources} غير متاح`
                }
              />

              <MetricCard
                icon={Network}
                label="الواجهة المختارة"
                value={
                  data.summary.selectedInterface ||
                  'غير متوفر'
                }
                description={
                  `${data.summary.activeInterfaceCount} واجهات نشطة`
                }
              />

              <MetricCard
                icon={Activity}
                label="إجمالي الحركة"
                value={
                  formatBitrate(
                    data.summary.currentTotalBps,
                  )
                }
                description={
                  `الاتجاه: ${data.traffic.trend}`
                }
              />

              <MetricCard
                icon={Router}
                label="الجهاز"
                value={
                  data.device.identity ||
                  data.routerIp
                }
                description={
                  data.device.reachable
                    ? 'RouterOS متاح'
                    : 'RouterOS غير متاح'
                }
              />
            </div>
          </section>

          <section className="network-intelligence-components">
            <MetricCard
              icon={Cpu}
              label="استخدام CPU"
              value={
                formatNumber(
                  data.device.cpuUsagePercent,
                  '%',
                  1,
                )
              }
              description={
                data.device.boardName ||
                'RouterOS Device'
              }
            />

            <MetricCard
              icon={Wifi}
              label="Ping Latency"
              value={
                formatNumber(
                  data.ping.latencyMs,
                  ' ms',
                  2,
                )
              }
              description={
                `Packet Loss: ` +
                formatNumber(
                  data.ping.packetLossPercent,
                  '%',
                  2,
                )
              }
            />

            <MetricCard
              icon={Signal}
              label="LTE RSRP"
              value={
                formatNumber(
                  data.lte.rsrp,
                  ' dBm',
                  1,
                )
              }
              description={
                `RSRQ: ` +
                formatNumber(
                  data.lte.rsrq,
                  ' dB',
                  1,
                )
              }
            />

            <MetricCard
              icon={RadioTower}
              label="LTE SINR"
              value={
                formatNumber(
                  data.lte.sinr,
                  ' dB',
                  1,
                )
              }
              description={
                [
                  data.lte.operator,
                  data.lte.band,
                ]
                  .filter(Boolean)
                  .join(' • ') ||
                'LTE غير متوفر'
              }
            />

            <MetricCard
              icon={Gauge}
              label="Download"
              value={
                formatBitrate(
                  data.traffic.rxBps,
                )
              }
              description={
                data.traffic.selectedInterface
              }
            />

            <MetricCard
              icon={Gauge}
              label="Upload"
              value={
                formatBitrate(
                  data.traffic.txBps,
                )
              }
              description={
                `${data.traffic.historyPoints} نقاط تاريخية`
              }
            />
          </section>

          <section className="network-intelligence-sources-section">
            <div className="network-intelligence-section-title">
              <div>
                <p className="eyebrow">
                  Data Sources
                </p>

                <h4>
                  حالة مصادر البيانات
                </h4>
              </div>

              <SSProgress
                value={
                  data.summary.totalSources > 0
                    ? (
                        data.summary.availableSources /
                        data.summary.totalSources
                      ) * 100
                    : 0
                }
                tone={
                  data.summary.unavailableSources === 0
                    ? 'success'
                    : 'warning'
                }
                size="sm"
                variant="soft"
                maximumFractionDigits={0}
                animated
              />
            </div>

            <div className="network-intelligence-sources">
              {data.sources.map(
                source => (
                  <SourceCard
                    key={source.name}
                    source={source}
                  />
                ),
              )}
            </div>
          </section>

          <section className="network-intelligence-detail-grid">
            <div>
              <div className="network-intelligence-section-title">
                <div>
                  <p className="eyebrow">
                    Findings
                  </p>

                  <h4>
                    نتائج التحليل
                  </h4>
                </div>

                <span>
                  {data.findings.length}
                </span>
              </div>

              <div className="network-intelligence-findings">
                {data.findings.length > 0 ? (
                  data.findings.map(
                    finding => (
                      <FindingCard
                        key={finding.id}
                        finding={finding}
                      />
                    ),
                  )
                ) : (
                  <div className="network-intelligence-empty">
                    <CheckCircle2 size={26} />

                    <strong>
                      لا توجد ملاحظات تشغيلية
                    </strong>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="network-intelligence-section-title">
                <div>
                  <p className="eyebrow">
                    Recommendations
                  </p>

                  <h4>
                    التوصيات
                  </h4>
                </div>

                <span>
                  {data.recommendations.length}
                </span>
              </div>

              <div className="network-intelligence-recommendations">
                {data.recommendations.length > 0 ? (
                  data.recommendations.map(
                    (recommendation, index) => (
                      <div
                        key={`${recommendation}-${index}`}
                      >
                        <span>
                          {index + 1}
                        </span>

                        <p>
                          {recommendation}
                        </p>
                      </div>
                    ),
                  )
                ) : (
                  <div className="network-intelligence-empty">
                    <CheckCircle2 size={26} />

                    <strong>
                      لا توجد توصيات عاجلة
                    </strong>
                  </div>
                )}
              </div>
            </div>
          </section>

          <footer className="network-intelligence-footer">
            <span>
              آخر تحديث: {formatDate(lastUpdated)}
            </span>

            <span>
              {data.analyzer.name}
              {data.analyzer.version
                ? ` v${data.analyzer.version}`
                : ''}
            </span>
          </footer>
        </>
      ) : (
        <div className="network-intelligence-empty">
          <AlertCircle size={30} />

          <strong>
            لا توجد بيانات Network Intelligence
          </strong>
        </div>
      )}
    </article>
  )
}
