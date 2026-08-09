import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Gauge,
  ListChecks,
  MemoryStick,
  Network,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'

import useExecutiveNarrative from '../../hooks/useExecutiveNarrative'

import {
  SSStatusChip,
} from '../ui'

import './ExecutiveNarrativeCard.css'


const PRIORITY_PRESENTATION = {
  critical: {
    label: 'حرجة',
    tone: 'danger',
    icon: ShieldAlert,
    className: 'critical',
  },

  high: {
    label: 'مرتفعة',
    tone: 'danger',
    icon: AlertTriangle,
    className: 'high',
  },

  medium: {
    label: 'متوسطة',
    tone: 'warning',
    icon: AlertTriangle,
    className: 'medium',
  },

  low: {
    label: 'منخفضة',
    tone: 'success',
    icon: CheckCircle2,
    className: 'low',
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

  notice: {
    label: 'تنبيه',
    icon: AlertCircle,
    className: 'notice',
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
  digits = 1,
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


function Metric({
  icon: Icon,
  label,
  value,
}) {
  return (
    <div className="executive-narrative-metric">
      <span>
        {Icon && <Icon size={17} />}
      </span>

      <div>
        <small>
          {label}
        </small>

        <strong>
          {value}
        </strong>
      </div>
    </div>
  )
}


function Observation({
  observation,
}) {
  const presentation =
    SEVERITY_PRESENTATION[
      observation.severity
    ] ||
    SEVERITY_PRESENTATION.info

  const Icon =
    presentation.icon

  return (
    <article
      className={
        `executive-narrative-observation ` +
        presentation.className
      }
    >
      <span>
        <Icon size={18} />
      </span>

      <div>
        <header>
          <strong>
            {observation.title}
          </strong>

          <small>
            {presentation.label}
          </small>
        </header>

        {observation.recommendation ? (
          <p>
            {observation.recommendation}
          </p>
        ) : null}
      </div>
    </article>
  )
}


export default function ExecutiveNarrativeCard({
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
  } = useExecutiveNarrative(
    ip,
    {
      includeHistory: true,
      historyMinutes: 15,
      historyWindowSeconds: 10,
      refreshInterval,
      enabled:
        Boolean(ip),
    },
  )



  if (loading && !data) {
    return (
      <article className="panel wide-panel executive-narrative-panel executive-narrative-loading">
        <Activity
          className="is-spinning"
          size={28}
        />

        <span>
          جارٍ إعداد الملخص التنفيذي...
        </span>
      </article>
    )
  }

  const priority =
    data?.priority ||
    'low'

  const presentation =
    PRIORITY_PRESENTATION[
      priority
    ] ||
    PRIORITY_PRESENTATION.low

  const PriorityIcon =
    presentation.icon

  return (
    <article
      className={
        `panel wide-panel executive-narrative-panel ` +
        presentation.className
      }
    >
      <header className="executive-narrative-header">
        <div className="executive-narrative-title">
          <span>
            <BrainCircuit size={25} />
          </span>

          <div>
            <p className="eyebrow">
              Executive AI Narrative
            </p>

            <h3>
              الملخص التنفيذي الذكي
            </h3>

            <small>
              تحويل مؤشرات الشبكة إلى قراءة إدارية واضحة
            </small>
          </div>
        </div>

        <div className="executive-narrative-actions">
          <SSStatusChip
            status={priority}
            label={
              `الأولوية ${presentation.label}`
            }
            tone={presentation.tone}
            showIcon
          />

          <button
            type="button"
            className="executive-narrative-refresh"
            onClick={refresh}
            disabled={
              loading ||
              refreshing
            }
          >
            <RefreshCw
              size={16}
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
        <div className="executive-narrative-error">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : null}

      {!data ? (
        <div className="executive-narrative-empty">
          لا توجد بيانات تنفيذية متاحة.
        </div>
      ) : (
        <>
          <section className="executive-narrative-hero">
            <div className="executive-narrative-headline">
              <span>
                <Sparkles size={24} />
              </span>

              <div>
                <h2>
                  {data.headline}
                </h2>

                <p>
                  {data.executiveSummary}
                </p>
              </div>
            </div>

            <div className="executive-narrative-score">
              <span>
                درجة الصحة
              </span>

              <strong>
                {formatNumber(
                  data.healthScore,
                  '%',
                  0,
                )}
              </strong>

              <small>
                الثقة{' '}
                {formatNumber(
                  data.confidencePercent,
                  '%',
                  0,
                )}
              </small>
            </div>
          </section>

          <section className="executive-narrative-summary-grid">
            <div>
              <h4>
                الملخص التشغيلي
              </h4>

              <p>
                {data.operationalSummary}
              </p>
            </div>

            <div
              className={
                data.requiresImmediateAction
                  ? 'requires-action'
                  : 'monitor-only'
              }
            >
              <h4>
                الأثر على الأعمال
              </h4>

              <p>
                {data.businessImpact}
              </p>

              <strong>
                <PriorityIcon size={17} />

                {data.requiresImmediateAction
                  ? 'يتطلب تدخلًا فوريًا'
                  : 'لا يتطلب تدخلًا فوريًا'}
              </strong>
            </div>
          </section>

          <section className="executive-narrative-metrics">
            <Metric
              icon={Database}
              label="مصادر البيانات"
              value={
                `${data.metrics.availableSources}` +
                ` / ${data.metrics.totalSources}`
              }
            />

            <Metric
              icon={Network}
              label="الواجهة الرئيسية"
              value={
                data.metrics.selectedInterface
              }
            />

            <Metric
              icon={Cpu}
              label="استخدام CPU"
              value={formatNumber(
                data.metrics.cpuUsagePercent,
                '%',
                0,
              )}
            />

            <section className="cpu-decision-intelligence">
              <h4>
                🧠 CPU Decision Intelligence
              </h4>

              <div>
                <strong>
                  الحالة:
                </strong>
                <span>
                  {data.metrics.cpuState || 'غير متوفر'}
                </span>
              </div>

              <div>
                <strong>
                  القرار:
                </strong>
                <span>
                  {data.metrics.cpuAction || 'غير متوفر'}
                </span>
              </div>

              <div>
                <strong>
                  السبب:
                </strong>
                <span>
                  {data.metrics.cpuReason || 'غير متوفر'}
                </span>
              </div>

              <div>
                <strong>
                  رسالة المشغل:
                </strong>
                <span>
                  {data.metrics.cpuOperatorMessage || 'غير متوفر'}
                </span>
              </div>
            </section>

            <Metric
              icon={MemoryStick}
              label="استخدام الذاكرة"
              value={formatNumber(
                data.metrics.memoryUsagePercent,
                '%',
                0,
              )}
            />

            <Metric
              icon={Clock3}
              label="زمن الاستجابة"
              value={formatNumber(
                data.metrics.latencyMs,
                ' ms',
                1,
              )}
            />

            <Metric
              icon={Gauge}
              label="فقدان الحزم"
              value={formatNumber(
                data.metrics.packetLossPercent,
                '%',
                1,
              )}
            />
          </section>
<section className="executive-historical-intelligence">

  <div className="executive-narrative-section-title">
    <h4>
      🧠 التحليل التاريخي الذكي
    </h4>
  </div>

  {data.historicalIntelligence?.cpu?.available ? (

    <div className="historical-grid">

      <Metric
        label="CPU الحالي"
        value={
          formatNumber(
            data.historicalIntelligence.cpu.current,
            '%',
            2
          )
        }
      />

      <Metric
        label="متوسط CPU"
        value={
          formatNumber(
            data.historicalIntelligence.cpu.average,
            '%',
            2
          )
        }
      />

      <Metric
        label="أعلى CPU"
        value={
          formatNumber(
            data.historicalIntelligence.cpu.maximum,
            '%',
            2
          )
        }
      />

      <Metric
        label="الاتجاه"
        value={
          data.historicalIntelligence.cpu.trend
        }
      />

      <Metric
        label="القرار"
        value={
          data.historicalIntelligence.cpu.decision
        }
      />

      <Metric
        label="العينات"
        value={
          data.historicalIntelligence.cpu.samples
        }
      />

    </div>

  ) : (

    <p>
      لا توجد بيانات تاريخية متاحة
    </p>

  )}

</section>

          <section className="executive-narrative-details">
            <div>
              <div className="executive-narrative-section-title">
                <h4>
                  أهم الملاحظات
                </h4>

                <span>
                  {data.observations.length}
                </span>
              </div>

              <div className="executive-narrative-observations">
                {data.observations.length ? (
                  data.observations.map(
                    observation => (
                      <Observation
                        key={observation.id}
                        observation={observation}
                      />
                    ),
                  )
                ) : (
                  <p className="executive-narrative-empty-text">
                    لا توجد ملاحظات تشغيلية مهمة.
                  </p>
                )}
              </div>
            </div>

            <div>
              <div className="executive-narrative-section-title">
                <h4>
                  الإجراءات الموصى بها
                </h4>

                <ListChecks size={18} />
              </div>

              <div className="executive-narrative-recommendations">
                {data.actions.map(
                  (action, index) => (
                    <div
                      key={
                        `${index}-${action}`
                      }
                    >
                      <span>
                        {index + 1}
                      </span>

                      <p>
                        {action}
                      </p>
                    </div>
                  ),
                )}
              </div>
            </div>
          </section>




          <footer className="executive-narrative-footer">
            <span>
              المحرك: {data.engine.name || 'SS4TS Executive Narrative'}
            </span>

            <span>
              آخر تحديث: {formatDate(lastUpdated)}
            </span>
          </footer>
        </>
      )}
    </article>
  )
}