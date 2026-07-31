import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  Activity,
  Download,
  Eye,
  EyeOff,
  Gauge,
  Maximize2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Signal,
  WifiOff,
} from 'lucide-react'

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import useTrafficHistory from '../../hooks/useTrafficHistory'
import { formatBitrate } from '../../utils/formatters'


const RANGE_OPTIONS = [
  {
    label: '5 دقائق',
    minutes: 5,
    window: 10,
  },
  {
    label: '15 دقيقة',
    minutes: 15,
    window: 10,
  },
  {
    label: 'ساعة',
    minutes: 60,
    window: 30,
  },
  {
    label: '6 ساعات',
    minutes: 360,
    window: 120,
  },
  {
    label: '24 ساعة',
    minutes: 1440,
    window: 300,
  },
]


function formatChartTime(value, minutes) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  if (minutes >= 1440) {
    return new Intl.DateTimeFormat('ar-SA', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  return new Intl.DateTimeFormat('ar-SA', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}


function formatFullTime(value) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  return new Intl.DateTimeFormat('ar-SA', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}


function calculateAverage(points, key) {
  if (!points.length) {
    return 0
  }

  return (
    points.reduce(
      (sum, point) =>
        sum + (Number(point[key]) || 0),
      0,
    ) / points.length
  )
}


function calculatePercentile(values, percentile) {
  const sortedValues = values
    .map((value) => Number(value) || 0)
    .sort((first, second) => first - second)

  if (!sortedValues.length) {
    return 0
  }

  const index = Math.ceil(
    (percentile / 100) * sortedValues.length,
  ) - 1

  return sortedValues[
    Math.max(
      0,
      Math.min(index, sortedValues.length - 1),
    )
  ]
}


function escapeCsvValue(value) {
  const stringValue = String(value ?? '')

  return `"${stringValue.replaceAll('"', '""')}"`
}


function SummaryCard({
  title,
  value,
  description,
  icon: Icon,
  tone = '',
}) {
  return (
    <div
      className={`enterprise-summary-card ${tone}`}
    >
      <div>
        <span>{title}</span>
        <strong>{value}</strong>

        {description && (
          <small>{description}</small>
        )}
      </div>

      <div className="enterprise-summary-icon">
        <Icon size={18} />
      </div>
    </div>
  )
}


function TrafficTooltip({
  active,
  payload,
  averageTotal,
  percentile95,
}) {
  if (!active || !payload?.length) {
    return null
  }

  const point = payload[0]?.payload

  if (!point) {
    return null
  }

  return (
    <div className="enterprise-traffic-tooltip pro">
      <div className="enterprise-tooltip-time">
        <Activity size={16} />

        <strong>
          {formatFullTime(point.time)}
        </strong>
      </div>

      <div className="enterprise-tooltip-row download">
        <span>⬇ Download</span>
        <strong>{formatBitrate(point.rx_bps)}</strong>
      </div>

      <div className="enterprise-tooltip-row upload">
        <span>⬆ Upload</span>
        <strong>{formatBitrate(point.tx_bps)}</strong>
      </div>

      <div className="enterprise-tooltip-row total">
        <span>إجمالي الحركة</span>
        <strong>{formatBitrate(point.total_bps)}</strong>
      </div>

      <div className="enterprise-tooltip-row average">
        <span>المتوسط</span>
        <strong>{formatBitrate(averageTotal)}</strong>
      </div>

      <div className="enterprise-tooltip-row percentile">
        <span>95th Percentile</span>
        <strong>{formatBitrate(percentile95)}</strong>
      </div>
    </div>
  )
}


export default function LiveTrafficChart({
  ip,
  interfaces = [],
  defaultInterface = '',
  selectedInterface: controlledInterface = '',
  onSelectInterface,
}) {
  const [
    internalSelectedInterface,
    setInternalSelectedInterface,
  ] = useState(
    controlledInterface ||
    defaultInterface,
  )

  const selectedInterface =
    controlledInterface ||
    internalSelectedInterface

  function updateSelectedInterface(
    interfaceName,
  ) {
    setInternalSelectedInterface(
      interfaceName,
    )

    if (
      typeof onSelectInterface ===
      'function'
    ) {
      onSelectInterface(
        interfaceName,
      )
    }
  }

  const [selectedRange, setSelectedRange] =
    useState(RANGE_OPTIONS[1])

  const [isPaused, setIsPaused] = useState(false)
  const [showDownload, setShowDownload] = useState(true)
  const [showUpload, setShowUpload] = useState(true)
  const [scaleMode, setScaleMode] = useState('auto')

  const [currentTime, setCurrentTime] =
    useState(Date.now())

  const [zoomStart, setZoomStart] = useState(null)
  const [zoomEnd, setZoomEnd] = useState(null)
  const [zoomDomain, setZoomDomain] = useState(null)

  const [hoverIndex, setHoverIndex] = useState(null)
  const [hoverTotal, setHoverTotal] = useState(null)

  useEffect(() => {
    const preferredInterface =
      controlledInterface ||
      defaultInterface

    if (
      preferredInterface &&
      internalSelectedInterface !==
        preferredInterface
    ) {
      setInternalSelectedInterface(
        preferredInterface,
      )
    }
  }, [
    controlledInterface,
    defaultInterface,
    internalSelectedInterface,
  ])

  useEffect(() => {
    const timerId = globalThis.setInterval(() => {
      setCurrentTime(Date.now())
    }, 1000)

    return () => {
      globalThis.clearInterval(timerId)
    }
  }, [])

  useEffect(() => {
    setZoomStart(null)
    setZoomEnd(null)
    setZoomDomain(null)
  }, [
    selectedInterface,
    selectedRange.minutes,
  ])

  const availableInterfaces = useMemo(() => {
    const interfaceNames = interfaces
      .map((item) => item.if_descr)
      .filter(Boolean)

    if (
      defaultInterface &&
      !interfaceNames.includes(defaultInterface)
    ) {
      interfaceNames.unshift(defaultInterface)
    }

    return [...new Set(interfaceNames)]
  }, [
    interfaces,
    defaultInterface,
  ])

  const {
    history,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh,
  } = useTrafficHistory({
    ip,
    interfaceName: selectedInterface,
    minutes: selectedRange.minutes,
    window: selectedRange.window,
    refreshInterval: 10000,
    enabled: !isPaused,
  })

  const chartData = useMemo(() => {
    return (history?.points || []).map(
      (point, index) => ({
        ...point,
        pointIndex: index,
        rx_bps: Number(point.rx_bps) || 0,
        tx_bps: Number(point.tx_bps) || 0,
        total_bps:
          Number(point.total_bps) ||
          (Number(point.rx_bps) || 0) +
            (Number(point.tx_bps) || 0),
        chartTime: formatChartTime(
          point.time,
          selectedRange.minutes,
        ),
      }),
    )
  }, [
    history,
    selectedRange.minutes,
  ])

  const visibleData = useMemo(() => {
    if (!zoomDomain) {
      return chartData
    }

    return chartData.filter(
      (point) =>
        point.pointIndex >= zoomDomain.left &&
        point.pointIndex <= zoomDomain.right,
    )
  }, [
    chartData,
    zoomDomain,
  ])

  const statistics = useMemo(() => {
    const latestPoint =
      chartData.length > 0
        ? chartData[chartData.length - 1]
        : null

    const peakTotal = chartData.reduce(
      (maximum, point) =>
        Math.max(
          maximum,
          point.total_bps,
        ),
      0,
    )

    const averageDownload = calculateAverage(
      chartData,
      'rx_bps',
    )

    const averageUpload = calculateAverage(
      chartData,
      'tx_bps',
    )

    const averageTotal = calculateAverage(
      chartData,
      'total_bps',
    )

    const percentile95 = calculatePercentile(
      chartData.map((point) => point.total_bps),
      95,
    )

    return {
      latestPoint,
      peakTotal,
      averageDownload,
      averageUpload,
      averageTotal,
      percentile95,
    }
  }, [chartData])

  const secondsSinceUpdate = lastUpdated
    ? Math.max(
        0,
        Math.floor(
          (currentTime - lastUpdated.getTime()) /
            1000,
        ),
      )
    : null

  const dataStatus = useMemo(() => {
    if (isPaused) {
      return {
        label: 'PAUSED',
        className: 'paused',
      }
    }

    if (error) {
      return {
        label: 'ERROR',
        className: 'offline',
      }
    }

    if (
      secondsSinceUpdate !== null &&
      secondsSinceUpdate <= 20
    ) {
      return {
        label: 'LIVE',
        className: 'online',
      }
    }

    return {
      label: 'STALE',
      className: 'stale',
    }
  }, [
    error,
    isPaused,
    secondsSinceUpdate,
  ])

  const fixedMaximum = useMemo(() => {
    if (!statistics.peakTotal) {
      return 1000000
    }

    const step = 1000000

    return (
      Math.ceil(
        statistics.peakTotal / step,
      ) *
      step *
      1.2
    )
  }, [statistics.peakTotal])

  const xDomain = zoomDomain
    ? [
        zoomDomain.left,
        zoomDomain.right,
      ]
    : ['dataMin', 'dataMax']

  const yDomain =
    scaleMode === 'fixed'
      ? [0, fixedMaximum]
      : [0, 'auto']

  function resetZoom() {
    setZoomStart(null)
    setZoomEnd(null)
    setZoomDomain(null)
  }

  function finishZoom() {
    if (
      zoomStart === null ||
      zoomEnd === null ||
      zoomStart === zoomEnd
    ) {
      setZoomStart(null)
      setZoomEnd(null)
      return
    }

    setZoomDomain({
      left: Math.min(zoomStart, zoomEnd),
      right: Math.max(zoomStart, zoomEnd),
    })

    setZoomStart(null)
    setZoomEnd(null)
  }

  function handleMouseMove(chartState) {
    if (
      zoomStart !== null &&
      chartState?.activeLabel !== undefined
    ) {
      setZoomEnd(Number(chartState.activeLabel))
    }

    const activePoint =
      chartState?.activePayload?.[0]?.payload

    if (activePoint) {
      setHoverIndex(activePoint.pointIndex)
      setHoverTotal(activePoint.total_bps)
    }
  }

  function exportCsv() {
    if (!chartData.length) {
      return
    }

    const header = [
      'Time',
      'Interface',
      'Download bps',
      'Upload bps',
      'Total bps',
    ]

    const rows = chartData.map((point) => [
      point.time,
      history?.interface ||
        selectedInterface ||
        '',
      point.rx_bps,
      point.tx_bps,
      point.total_bps,
    ])

    const csvContent = [
      header,
      ...rows,
    ]
      .map((row) =>
        row
          .map(escapeCsvValue)
          .join(','),
      )
      .join('\n')

    const blob = new Blob(
      [`\uFEFF${csvContent}`],
      {
        type: 'text/csv;charset=utf-8;',
      },
    )

    const downloadUrl =
      globalThis.URL.createObjectURL(blob)

    const anchor =
      globalThis.document.createElement('a')

    anchor.href = downloadUrl
    anchor.download =
      `ss4ts-traffic-${ip}-${selectedRange.minutes}m.csv`

    globalThis.document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()

    globalThis.URL.revokeObjectURL(downloadUrl)
  }

  const latestIndex =
    statistics.latestPoint?.pointIndex ?? null

  return (
    <article className="panel enterprise-traffic-panel pro">
      <div className="enterprise-traffic-header">
        <div className="enterprise-traffic-title">
          <div className="enterprise-title-line">
            <div>
              <p className="eyebrow">
                Enterprise Chart Pro
              </p>

              <h3>تحليل حركة الشبكة الحية</h3>
            </div>

            <span
              className={`enterprise-live-badge ${dataStatus.className}`}
            >
              <i />
              {dataStatus.label}
            </span>
          </div>

          <p className="enterprise-update-text">
            {lastUpdated
              ? `آخر تحديث منذ ${secondsSinceUpdate} ثانية`
              : 'في انتظار أول تحديث...'}
          </p>
        </div>

        <div className="enterprise-header-actions pro-actions">
          <button
            type="button"
            className="enterprise-action-button"
            onClick={() => setIsPaused(
              (currentValue) => !currentValue,
            )}
          >
            {isPaused ? (
              <>
                <Play size={17} />
                تشغيل
              </>
            ) : (
              <>
                <Pause size={17} />
                إيقاف مؤقت
              </>
            )}
          </button>

          <button
            type="button"
            className="enterprise-action-button"
            onClick={resetZoom}
            disabled={!zoomDomain}
          >
            <RotateCcw size={17} />
            Reset Zoom
          </button>

          <button
            type="button"
            className="enterprise-action-button"
            onClick={exportCsv}
            disabled={!chartData.length}
          >
            <Download size={17} />
            CSV
          </button>

          <button
            type="button"
            className="enterprise-action-button refresh"
            onClick={refresh}
            disabled={refreshing || isPaused}
          >
            <RefreshCw
              size={17}
              className={
                refreshing ? 'is-spinning' : ''
              }
            />

            تحديث
          </button>
        </div>
      </div>

      <div className="enterprise-pro-toolbar">
        <label>
          <span>واجهة الشبكة</span>

          <select
            value={selectedInterface}
            onChange={(event) =>
              updateSelectedInterface(
                event.target.value,
              )
            }
          >
            {availableInterfaces.map(
              (interfaceName) => (
                <option
                  value={interfaceName}
                  key={interfaceName}
                >
                  {interfaceName}
                </option>
              ),
            )}
          </select>
        </label>

        <div className="enterprise-range-buttons">
          {RANGE_OPTIONS.map((option) => (
            <button
              type="button"
              key={option.minutes}
              className={
                selectedRange.minutes ===
                option.minutes
                  ? 'active'
                  : ''
              }
              onClick={() =>
                setSelectedRange(option)
              }
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="enterprise-chart-switches">
          <button
            type="button"
            className={showDownload ? 'active download' : ''}
            onClick={() =>
              setShowDownload(
                (currentValue) => !currentValue,
              )
            }
          >
            {showDownload
              ? <Eye size={16} />
              : <EyeOff size={16} />}

            Download
          </button>

          <button
            type="button"
            className={showUpload ? 'active upload' : ''}
            onClick={() =>
              setShowUpload(
                (currentValue) => !currentValue,
              )
            }
          >
            {showUpload
              ? <Eye size={16} />
              : <EyeOff size={16} />}

            Upload
          </button>

          <button
            type="button"
            className={
              scaleMode === 'auto'
                ? 'active'
                : ''
            }
            onClick={() => setScaleMode('auto')}
          >
            <Maximize2 size={16} />
            Auto Scale
          </button>

          <button
            type="button"
            className={
              scaleMode === 'fixed'
                ? 'active'
                : ''
            }
            onClick={() => setScaleMode('fixed')}
          >
            <Gauge size={16} />
            Fixed Scale
          </button>
        </div>
      </div>

      <div className="enterprise-traffic-summary pro-summary">
        <SummaryCard
          title="Current Total"
          value={formatBitrate(
            statistics.latestPoint?.total_bps,
          )}
          description="Current total speed"
          icon={Activity}
          tone="download"
        />

        <SummaryCard
          title="Download الحالي"
          value={formatBitrate(
            statistics.latestPoint?.rx_bps,
          )}
          description="Current inbound"
          icon={Signal}
          tone="download"
        />

        <SummaryCard
          title="Upload الحالي"
          value={formatBitrate(
            statistics.latestPoint?.tx_bps,
          )}
          description="Current outbound"
          icon={Signal}
          tone="upload"
        />

        <SummaryCard
          title="Average"
          value={formatBitrate(
            statistics.averageTotal,
          )}
          description="Average total traffic"
          icon={Gauge}
          tone="average"
        />

        <SummaryCard
          title="Peak"
          value={formatBitrate(
            statistics.peakTotal,
          )}
          description="Highest traffic"
          icon={Activity}
          tone="peak"
        />

        <SummaryCard
          title="95th Percentile"
          value={formatBitrate(
            statistics.percentile95,
          )}
          description="Sustained usage level"
          icon={Gauge}
          tone="percentile"
        />
      </div>

      {error && (
        <div className="enterprise-chart-message error">
          {error}
        </div>
      )}

      {loading && !chartData.length ? (
        <div className="enterprise-chart-message">
          <RefreshCw
            className="is-spinning"
            size={28}
          />

          جارٍ تحليل حركة الشبكة...
        </div>
      ) : chartData.length === 0 ? (
        <div className="enterprise-chart-message">
          <WifiOff size={32} />
          لا توجد بيانات تاريخية.
        </div>
      ) : (
        <>
          <div className="enterprise-zoom-hint">
            اسحب داخل الرسم لتكبير فترة محددة
          </div>

          <div className="enterprise-chart-container pro-chart">
            <ResponsiveContainer
              width="100%"
              height={500}
            >
              <AreaChart
                data={visibleData}
                margin={{
                  top: 28,
                  right: 28,
                  left: 20,
                  bottom: 8,
                }}
                onMouseDown={(chartState) => {
                  if (
                    chartState?.activeLabel !== undefined
                  ) {
                    setZoomStart(
                      Number(chartState.activeLabel),
                    )
                    setZoomEnd(
                      Number(chartState.activeLabel),
                    )
                  }
                }}
                onMouseMove={handleMouseMove}
                onMouseUp={finishZoom}
                onMouseLeave={() => {
                  setHoverIndex(null)
                  setHoverTotal(null)
                }}
              >
                <defs>
                  <linearGradient
                    id="proDownloadGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="#10b981"
                      stopOpacity={0.42}
                    />
                    <stop
                      offset="100%"
                      stopColor="#10b981"
                      stopOpacity={0}
                    />
                  </linearGradient>

                  <linearGradient
                    id="proUploadGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="#8b5cf6"
                      stopOpacity={0.35}
                    />
                    <stop
                      offset="100%"
                      stopColor="#8b5cf6"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  strokeDasharray="4 6"
                  vertical={false}
                  stroke="rgba(148, 163, 184, 0.13)"
                />

                <XAxis
                  type="number"
                  dataKey="pointIndex"
                  domain={xDomain}
                  allowDataOverflow
                  tickFormatter={(pointIndex) =>
                    chartData[
                      Math.round(pointIndex)
                    ]?.chartTime || ''
                  }
                  tickLine={false}
                  axisLine={false}
                  minTickGap={45}
                  tick={{
                    fill: '#7890ad',
                    fontSize: 11,
                  }}
                />

                <YAxis
                  domain={yDomain}
                  allowDataOverflow={
                    scaleMode === 'fixed'
                  }
                  tickFormatter={formatBitrate}
                  width={95}
                  tickLine={false}
                  axisLine={false}
                  tick={{
                    fill: '#7890ad',
                    fontSize: 11,
                  }}
                />

                <Tooltip
                  content={
                    <TrafficTooltip
                      averageTotal={
                        statistics.averageTotal
                      }
                      percentile95={
                        statistics.percentile95
                      }
                    />
                  }
                  cursor={{
                    stroke:
                      'rgba(96, 165, 250, 0.7)',
                    strokeWidth: 1,
                    strokeDasharray: '4 4',
                  }}
                />

                <Legend />

                <ReferenceLine
                  y={statistics.averageTotal}
                  stroke="#38bdf8"
                  strokeDasharray="7 6"
                  label={{
                    value: `AVG ${formatBitrate(
                      statistics.averageTotal,
                    )}`,
                    fill: '#38bdf8',
                    fontSize: 11,
                    position: 'insideTopLeft',
                  }}
                />

                <ReferenceLine
                  y={statistics.percentile95}
                  stroke="#f59e0b"
                  strokeDasharray="5 5"
                  label={{
                    value: `P95 ${formatBitrate(
                      statistics.percentile95,
                    )}`,
                    fill: '#fbbf24',
                    fontSize: 11,
                    position: 'insideTopRight',
                  }}
                />

                {hoverTotal !== null && (
                  <ReferenceLine
                    y={hoverTotal}
                    stroke="rgba(148, 163, 184, 0.4)"
                    strokeDasharray="3 4"
                  />
                )}

                {hoverIndex !== null && (
                  <ReferenceLine
                    x={hoverIndex}
                    stroke="rgba(96, 165, 250, 0.55)"
                    strokeDasharray="3 4"
                  />
                )}

                {showDownload && (
                  <Area
                    type="monotone"
                    dataKey="rx_bps"
                    name="Download"
                    stroke="#10b981"
                    fill="url(#proDownloadGradient)"
                    strokeWidth={3.5}
                    dot={false}
                    activeDot={{ r: 5 }}
                    isAnimationActive={!isPaused}
                    animationDuration={500}
                  />
                )}

                {showUpload && (
                  <Area
                    type="monotone"
                    dataKey="tx_bps"
                    name="Upload"
                    stroke="#8b5cf6"
                    fill="url(#proUploadGradient)"
                    strokeWidth={3.3}
                    dot={false}
                    activeDot={{ r: 5 }}
                    isAnimationActive={!isPaused}
                    animationDuration={500}
                  />
                )}

                {latestIndex !== null &&
                  showDownload && (
                    <ReferenceDot
                      x={latestIndex}
                      y={
                        statistics.latestPoint.rx_bps
                      }
                      r={6}
                      fill="#10b981"
                      stroke="#d1fae5"
                      strokeWidth={2}
                      className="enterprise-now-dot"
                      label={{
                        value: 'NOW',
                        position: 'top',
                        fill: '#34d399',
                        fontSize: 10,
                      }}
                    />
                  )}

                {zoomStart !== null &&
                  zoomEnd !== null && (
                    <ReferenceArea
                      x1={zoomStart}
                      x2={zoomEnd}
                      fill="#3b82f6"
                      fillOpacity={0.16}
                      strokeOpacity={0.4}
                    />
                  )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </article>
  )
}
