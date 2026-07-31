import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  Lightbulb,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
  Wrench,
  XCircle,
} from 'lucide-react'

import useDecisionIntelligence from '../../hooks/useDecisionIntelligence'

import {
  SSGauge,
  SSProgress,
  SSStatusChip,
  SSTable,
} from '../ui'

import './DecisionIntelligenceCenter.css'


const RISK_CONFIG = {
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
  medium: {
    label: 'متوسط',
    icon: AlertCircle,
    className: 'medium',
  },
  low: {
    label: 'منخفض',
    icon: Activity,
    className: 'low',
  },
  healthy: {
    label: 'سليم',
    icon: CheckCircle2,
    className: 'healthy',
  },
  unknown: {
    label: 'غير معروف',
    icon: AlertCircle,
    className: 'unknown',
  },
}

const QUALITY_CONFIG = {
  excellent: {
    label: 'ممتازة',
    className: 'excellent',
  },
  good: {
    label: 'جيدة',
    className: 'good',
  },
  degraded: {
    label: 'منخفضة',
    className: 'degraded',
  },
  poor: {
    label: 'ضعيفة',
    className: 'poor',
  },
  empty: {
    label: 'لا توجد بيانات',
    className: 'empty',
  },
  unknown: {
    label: 'غير معروفة',
    className: 'unknown',
  },
}

const SOURCE_LABELS = {
  routeros: 'RouterOS',
  interfaces: 'Interfaces',
  traffic_history: 'Traffic History',
}


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


function formatNumber(value) {
  const numericValue = Number(value)

  if (!Number.isFinite(numericValue)) {
    return '0'
  }

  return new Intl.NumberFormat('ar-SA', {
    maximumFractionDigits: 2,
  }).format(numericValue)
}


function formatDate(value) {
  if (!value) {
    return 'لم يتم التحديث بعد'
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


function getConfidence(item) {
  return clampPercent(
    item?.confidence_percent ??
      item?.confidence ??
      0,
  )
}


function getItemId(item) {
  return (
    item?.id ||
    item?.signal_id ||
    item?.cause_id ||
    item?.recommendation_id ||
    item?.decision_id ||
    ''
  )
}


function getInterfaceName(item) {
  return (
    item?.interface_name ||
    item?.interface ||
    ''
  )
}


function ConfidenceBar({
  value,
}) {
  const safeValue =
    clampPercent(value)

  const tone =
    safeValue >= 85
      ? 'success'
      : safeValue >= 65
        ? 'primary'
        : safeValue >= 40
          ? 'warning'
          : 'danger'

  return (
    <SSProgress
      className="decision-confidence"
      label="درجة الثقة"
      value={safeValue}
      tone={tone}
      size="sm"
      variant="soft"
      maximumFractionDigits={2}
      animated
    />
  )
}


function EvidenceList({
  evidence = [],
}) {
  if (
    !Array.isArray(evidence) ||
    evidence.length === 0
  ) {
    return (
      <p className="decision-empty-text">
        لا توجد أدلة تفصيلية متاحة.
      </p>
    )
  }

  return (
    <div className="decision-evidence-list">
      {evidence
        .slice(0, 6)
        .map((item, index) => {
          const key =
            item?.key ||
            item?.label ||
            `evidence-${index}`

          const label =
            item?.label ||
            item?.key ||
            'Evidence'

          const rawValue =
            item?.value

          const displayValue =
            typeof rawValue ===
            'boolean'
              ? rawValue
                ? 'نعم'
                : 'لا'
              : rawValue ??
                'غير معروف'

          return (
            <div
              className="decision-evidence-item"
              key={`${key}-${index}`}
            >
              <span className="decision-evidence-item__label">
                {label}
              </span>

              <strong className="decision-evidence-item__value">
                {String(
                  displayValue,
                )}

                {item?.unit
                  ? ` ${item.unit}`
                  : ''}
              </strong>
            </div>
          )
        })}
    </div>
  )
}


function DecisionChainCard({
  index,
  icon: Icon,
  label,
  title,
  description,
  item,
  tone,
  children,
}) {
  const interfaceName =
    getInterfaceName(item)

  const confidence =
    getConfidence(item)

  return (
    <article
      className={
        `decision-chain-card ` +
        `decision-chain-card--${tone}`
      }
    >
      <header className="decision-chain-card__header">
        <div className="decision-chain-card__identity">
          <span className="decision-chain-card__number">
            {index}
          </span>

          <span className="decision-chain-card__icon">
            <Icon size={21} />
          </span>

          <div>
            <span className="decision-chain-card__label">
              {label}
            </span>

            <h4>
              {title ||
                'لا توجد بيانات'}
            </h4>
          </div>
        </div>

        {item?.risk ? (
          <SSStatusChip
            status={item.risk}
            size="sm"
            showIcon
          />
        ) : null}
      </header>

      {description ? (
        <p className="decision-chain-card__description">
          {description}
        </p>
      ) : (
        <p className="decision-empty-text">
          لا توجد تفاصيل إضافية.
        </p>
      )}

      <div className="decision-chain-card__meta">
        {interfaceName ? (
          <span>
            <Network size={14} />
            {interfaceName}
          </span>
        ) : null}

        {getItemId(item) ? (
          <span
            title={getItemId(item)}
          >
            <Target size={14} />
            {getItemId(item)}
          </span>
        ) : null}
      </div>

      {confidence > 0 ? (
        <ConfidenceBar
          value={confidence}
        />
      ) : null}

      {children}
    </article>
  )
}


function ChainConnector() {
  return (
    <div className="decision-chain-connector">
      <span>
        <ArrowDown size={18} />
      </span>
    </div>
  )
}


function DataQualityCard({
  dataQuality,
}) {
  const quality =
    dataQuality?.quality ||
    'unknown'

  const qualityConfig =
    QUALITY_CONFIG[quality] ||
    QUALITY_CONFIG.unknown

  const completeness =
    clampPercent(
      dataQuality
        ?.completenessPercent,
    )

  const sampleCount =
    Number(
      dataQuality?.sampleCount ||
      0,
    )

  return (
    <section className="decision-quality-card">
      <div className="decision-quality-card__header">
        <div>
          <span className="decision-section-kicker">
            DATA QUALITY
          </span>

          <h3>جودة بيانات التحليل</h3>
        </div>

        <span
          className={
            `decision-quality-badge ` +
            `decision-quality-badge--${qualityConfig.className}`
          }
        >
          <Database size={15} />
          {qualityConfig.label}
        </span>
      </div>

      <div className="decision-quality-grid">
        <div className="decision-quality-metric">
          <span>اكتمال البيانات</span>

          <strong>
            {formatNumber(
              completeness,
            )}
            %
          </strong>

          <SSProgress
            className="decision-quality-progress"
            value={completeness}
            tone={
              completeness >= 90
                ? 'success'
                : completeness >= 70
                  ? 'primary'
                  : completeness >= 40
                    ? 'warning'
                    : 'danger'
            }
            size="xs"
            variant="soft"
            showValue={false}
            animated
          />
        </div>

        <div className="decision-quality-metric">
          <span>عدد العينات</span>

          <strong>
            {formatNumber(
              sampleCount,
            )}
          </strong>
        </div>

        <div className="decision-quality-metric">
          <span>حالة البيانات</span>

          <strong>
            {dataQuality?.partialData
              ? 'جزئية'
              : 'مكتملة'}
          </strong>
        </div>
      </div>
    </section>
  )
}


function DataSourcesCard({
  sources = {},
}) {
  const entries =
    Object.entries(sources)

  return (
    <section className="decision-sources-card">
      <div className="decision-sources-card__header">
        <div>
          <span className="decision-section-kicker">
            DATA SOURCES
          </span>

          <h3>مصادر التحليل</h3>
        </div>

        <Database size={21} />
      </div>

      <div className="decision-source-list">
        {entries.length === 0 ? (
          <p className="decision-empty-text">
            لا توجد معلومات عن مصادر البيانات.
          </p>
        ) : (
          entries.map(
            ([
              sourceName,
              source,
            ]) => {
              const available =
                Boolean(
                  source?.available,
                )

              return (
                <div
                  className="decision-source-item"
                  key={sourceName}
                >
                  <span
                    className={
                      available
                        ? 'decision-source-item__status decision-source-item__status--up'
                        : 'decision-source-item__status decision-source-item__status--down'
                    }
                  >
                    {available ? (
                      <CheckCircle2
                        size={16}
                      />
                    ) : (
                      <XCircle
                        size={16}
                      />
                    )}
                  </span>

                  <div className="decision-source-item__body">
                    <strong>
                      {SOURCE_LABELS[
                        sourceName
                      ] || sourceName}
                    </strong>

                    <span>
                      {available
                        ? 'متاح'
                        : source?.error ||
                          'غير متاح'}
                    </span>
                  </div>

                  {source?.item_count !==
                  undefined ? (
                    <span className="decision-source-item__count">
                      {formatNumber(
                        source.item_count,
                      )}
                    </span>
                  ) : null}
                </div>
              )
            },
          )
        )}
      </div>
    </section>
  )
}


function LoadingState() {
  return (
    <section className="decision-center decision-center--loading">
      <div className="decision-loading-icon">
        <BrainCircuit size={34} />
      </div>

      <h3>
        جارٍ تشغيل محرك تحليل القرار
      </h3>

      <p>
        يتم الآن تحليل حالة الجهاز،
        الواجهات، الأخطاء وحركة المرور.
      </p>

      <div className="decision-loading-lines">
        <span />
        <span />
        <span />
      </div>
    </section>
  )
}


function ErrorState({
  error,
  onRetry,
}) {
  return (
    <section className="decision-center decision-center--error">
      <div className="decision-error-icon">
        <AlertTriangle size={32} />
      </div>

      <div>
        <h3>
          تعذر تحميل Decision Intelligence
        </h3>

        <p>
          {error ||
            'حدث خطأ غير معروف أثناء التحليل.'}
        </p>
      </div>

      <button
        className="decision-button"
        type="button"
        onClick={onRetry}
      >
        <RefreshCw size={17} />
        إعادة المحاولة
      </button>
    </section>
  )
}



const DECISION_PILOT_COLUMNS = [
  {
    key: 'stage',
    header: 'المرحلة',
    minWidth: 150,
    cell: ({ row }) => (
      <div className="decision-pilot-stage">
        <strong>{row.stage}</strong>
        <span>{row.stageEnglish}</span>
      </div>
    ),
  },
  {
    key: 'title',
    header: 'العنوان',
    minWidth: 220,
    accessorKey: 'title',
  },
  {
    key: 'description',
    header: 'التفاصيل',
    minWidth: 320,
    accessorKey: 'description',
  },
  {
    key: 'status',
    header: 'الحالة',
    minWidth: 120,
    cell: ({ row }) => (
      <SSStatusChip
        status={row.status}
        label={row.statusLabel}
        size="sm"
      />
    ),
  },
]

export default function DecisionIntelligenceCenter({
  ip,
  selectedInterface = '',
  minutes = 15,
  windowSeconds = 10,
  refreshInterval = 30000,
  enabled = true,
}) {
  const {
    data,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh,
    riskLevel,
    riskScore,
    executiveSummary,
    primarySignal,
    primaryRootCause,
    primaryRecommendation,
    primaryDecision,
    dataQuality,
  } = useDecisionIntelligence(
    ip,
    {
      interfaceName:
        selectedInterface,
      minutes,
      windowSeconds,
      refreshInterval,
      enabled,
    },
  )

  if (
    loading &&
    !data
  ) {
    return <LoadingState />
  }

  if (
    error &&
    !data
  ) {
    return (
      <ErrorState
        error={error}
        onRetry={refresh}
      />
    )
  }

  if (!data) {
    return null
  }

  const riskConfig =
    RISK_CONFIG[riskLevel] ||
    RISK_CONFIG.unknown

  const RiskIcon =
    riskConfig.icon

  const evidence =
    primarySignal?.evidence ||
    primaryRootCause?.evidence ||
    []


  const decisionPilotRows = [
    {
      id: 'signal',
      stage: 'الإشارة',
      stageEnglish: 'Top Signal',
      title:
        primarySignal?.title ||
        'لا توجد إشارة',
      description:
        primarySignal?.description ||
        'لا توجد تفاصيل متاحة.',
      status:
        primarySignal?.risk ||
        'unknown',
      statusLabel:
        riskConfig.label,
    },
    {
      id: 'root-cause',
      stage: 'السبب الجذري',
      stageEnglish: 'Root Cause',
      title:
        primaryRootCause?.title ||
        'لا يوجد سبب جذري',
      description:
        primaryRootCause?.description ||
        'لا توجد تفاصيل متاحة.',
      status:
        primaryRootCause?.risk ||
        'unknown',
      statusLabel:
        primaryRootCause?.risk ||
        'غير معروف',
    },
    {
      id: 'recommendation',
      stage: 'التوصية',
      stageEnglish: 'Recommendation',
      title:
        primaryRecommendation?.title ||
        'لا توجد توصية',
      description:
        primaryRecommendation?.action ||
        'لا توجد تفاصيل متاحة.',
      status:
        primaryRecommendation?.priority ||
        'proposed',
      statusLabel:
        primaryRecommendation?.priority ||
        'مقترح',
    },
    {
      id: 'decision',
      stage: 'القرار',
      stageEnglish: 'Decision',
      title:
        primaryDecision?.title ||
        'لا يوجد قرار',
      description:
        primaryDecision?.action ||
        primaryDecision?.reason ||
        'لا توجد تفاصيل متاحة.',
      status:
        primaryDecision?.status ||
        'proposed',
      statusLabel:
        primaryDecision?.status ||
        'مقترح',
    },
  ]

  return (
    <section
      className={
        `decision-center ` +
        `decision-center--${riskConfig.className}`
      }
      dir="rtl"
    >
      <header className="decision-center__hero">
        <div className="decision-center__hero-content">
          <div className="decision-center__title-row">
            <span className="decision-center__brand-icon">
              <BrainCircuit size={27} />
            </span>

            <div>
              <span className="decision-section-kicker">
                DECISION INTELLIGENCE
              </span>

              <h2>
                مركز ذكاء القرار
              </h2>

              <p>
                تحليل مترابط يساعد المهندس على
                فهم المشكلة واتخاذ الإجراء الصحيح.
              </p>
            </div>
          </div>

          <div className="decision-center__actions">
            <span className="decision-center__updated">
              <Clock3 size={15} />

              آخر تحديث:
              {' '}
              {formatDate(
                lastUpdated,
              )}
            </span>

            <button
              className="decision-button decision-button--ghost"
              type="button"
              onClick={refresh}
              disabled={refreshing}
            >
              <RefreshCw
                size={17}
                className={
                  refreshing
                    ? 'decision-spin'
                    : ''
                }
              />

              {refreshing
                ? 'جارٍ التحديث'
                : 'تحديث التحليل'}
            </button>
          </div>
        </div>

        <div className="decision-risk-score">
          <SSGauge
            className="decision-risk-score__gauge"
            value={riskScore}
            min={0}
            max={100}
            valueSuffix="/100"
            tone={
              riskLevel === 'healthy'
                ? 'success'
                : riskLevel === 'low'
                  ? 'info'
                  : riskLevel === 'medium'
                    ? 'warning'
                    : riskLevel === 'high' ||
                        riskLevel === 'critical'
                      ? 'danger'
                      : 'neutral'
            }
            size="md"
            thickness={9}
            maximumFractionDigits={1}
            animated
          />

          <div className="decision-risk-score__label">
            <RiskIcon size={19} />

            <div>
              <span>مستوى الخطر</span>

              <strong>
                {riskConfig.label}
              </strong>
            </div>
          </div>
        </div>
      </header>

      <section className="decision-summary">
        <div className="decision-summary__icon">
          <Sparkles size={22} />
        </div>

        <div>
          <span className="decision-section-kicker">
            EXECUTIVE SUMMARY
          </span>

          <h3>الخلاصة التنفيذية</h3>

          <p>
            {executiveSummary ||
              'لم يتم إنشاء خلاصة تنفيذية بعد.'}
          </p>
        </div>
      </section>

      {error ? (
        <div className="decision-inline-warning">
          <AlertTriangle size={17} />

          <span>
            تم الاحتفاظ بآخر نتيجة ناجحة،
            لكن التحديث الأخير فشل:
            {' '}
            {error}
          </span>
        </div>
      ) : null}

      <div className="decision-chain-heading">
        <div>
          <span className="decision-section-kicker">
            ENGINEERING DECISION CHAIN
          </span>

          <h3>سلسلة التحليل والقرار</h3>
        </div>

        <span className="decision-chain-heading__interface">
          <Network size={16} />

          {selectedInterface ||
            data?.analysis_context
              ?.selected_interface ||
            'All Interfaces'}
        </span>
      </div>

      <div className="decision-chain">
        <DecisionChainCard
          index="01"
          icon={Activity}
          label="TOP SIGNAL"
          title={
            primarySignal?.title
          }
          description={
            primarySignal?.description
          }
          item={primarySignal}
          tone="signal"
        />

        <ChainConnector />

        <DecisionChainCard
          index="02"
          icon={Search}
          label="PROBABLE ROOT CAUSE"
          title={
            primaryRootCause?.title
          }
          description={
            primaryRootCause
              ?.description
          }
          item={primaryRootCause}
          tone="cause"
        />

        <ChainConnector />

        <DecisionChainCard
          index="03"
          icon={Lightbulb}
          label="RECOMMENDED ACTION"
          title={
            primaryRecommendation
              ?.title
          }
          description={
            primaryRecommendation
              ?.action
          }
          item={primaryRecommendation}
          tone="recommendation"
        >
          {primaryRecommendation
            ?.expected_impact ? (
            <div className="decision-impact">
              <Target size={15} />

              <span>
                <strong>
                  التأثير المتوقع:
                </strong>
                {' '}
                {
                  primaryRecommendation
                    .expected_impact
                }
              </span>
            </div>
          ) : null}
        </DecisionChainCard>

        <ChainConnector />

        <DecisionChainCard
          index="04"
          icon={Wrench}
          label="PROPOSED DECISION"
          title={
            primaryDecision?.title
          }
          description={
            primaryDecision?.action
          }
          item={primaryDecision}
          tone="decision"
        >
          {primaryDecision?.reason ? (
            <div className="decision-impact">
              <BrainCircuit size={15} />

              <span>
                <strong>
                  سبب القرار:
                </strong>
                {' '}
                {primaryDecision.reason}
              </span>
            </div>
          ) : null}
        </DecisionChainCard>
      </div>

      <section className="decision-pilot-table">
        <div className="decision-pilot-table__header">
          <div>
            <span className="decision-section-kicker">
              SSTABLE PILOT
            </span>

            <h3>ملخص سلسلة القرار</h3>
          </div>
        </div>

        <SSTable
          columns={DECISION_PILOT_COLUMNS}
          rows={decisionPilotRows}
          rowKey="id"
          density="compact"
          stickyHeader
          striped
          hoverable
          bordered
          emptyTitle="لا توجد بيانات للقرار"
          emptyDescription="لم ينتج التحليل الحالي عناصر قابلة للعرض."
        />
      </section>

      <div className="decision-details-grid">
        <section className="decision-evidence-card">
          <div className="decision-evidence-card__header">
            <div>
              <span className="decision-section-kicker">
                EXPLAINABILITY
              </span>

              <h3>الأدلة الداعمة</h3>
            </div>

            <Gauge size={21} />
          </div>

          <EvidenceList
            evidence={evidence}
          />
        </section>

        <DataQualityCard
          dataQuality={dataQuality}
        />

        <DataSourcesCard
          sources={
            dataQuality?.sources
          }
        />
      </div>

      <footer className="decision-center__footer">
        <span>
          <BrainCircuit size={15} />
          SS4TS Decision Intelligence Engine
        </span>

        <span>
          Domain Integration:
          {' '}
          {data?.domainIntegration
            ?.enabled
            ? 'Enabled'
            : 'Disabled'}
        </span>

        <span>
          Version:
          {' '}
          {data?.domainIntegration
            ?.version ||
            data?.engine?.version ||
            '1.6'}
        </span>
      </footer>
    </section>
  )
}
