import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowDownUp,
  ArrowUp,
  Cable,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleOff,
  Download,
  EthernetPort,
  Network,
  RadioTower,
  RefreshCw,
  Router,
  Search,
  Shield,
  SlidersHorizontal,
  Unplug,
  Waves,
} from 'lucide-react'

import useInterfaces from '../../hooks/useInterfaces'

import {
  SSMetric,
  SSProgress,
  SSStatusChip,
} from '../ui'
import { formatBitrate } from '../../utils/formatters'


const SORT_FIELDS = {
  interface: 'if_descr',
  index: 'if_index',
  type: 'if_type',
  status: 'is_oper_up',
  speed: 'speed_bps',
  download: 'rx_bps',
  upload: 'tx_bps',
  utilization: 'utilization_percent',
  errors: 'total_errors',
  mtu: 'mtu',
}


const FILTER_OPTIONS = [
  {
    value: 'all',
    label: 'جميع الواجهات',
  },
  {
    value: 'up',
    label: 'تعمل',
  },
  {
    value: 'down',
    label: 'متوقفة',
  },
  {
    value: 'errors',
    label: 'تحتوي أخطاء',
  },
  {
    value: 'traffic',
    label: 'بها حركة',
  },
]


function formatSpeed(value) {
  const speed = Number(value) || 0

  if (speed <= 0) {
    return 'غير محددة'
  }

  if (speed >= 1_000_000_000) {
    return `${(
      speed / 1_000_000_000
    ).toFixed(
      speed % 1_000_000_000 === 0
        ? 0
        : 1,
    )} Gbps`
  }

  if (speed >= 1_000_000) {
    return `${(
      speed / 1_000_000
    ).toFixed(
      speed % 1_000_000 === 0
        ? 0
        : 1,
    )} Mbps`
  }

  if (speed >= 1_000) {
    return `${(
      speed / 1_000
    ).toFixed(1)} Kbps`
  }

  return `${speed} bps`
}


function formatLastUpdated(value) {
  if (!value) {
    return 'غير متوفر'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'غير متوفر'
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


function getInterfacePresentation(item) {
  const name =
    String(item?.if_descr || '')
      .toLowerCase()

  const type =
    String(item?.if_type || '')
      .toLowerCase()

  if (
    name.startsWith('wg') ||
    name.includes('wireguard')
  ) {
    return {
      label: 'WireGuard',
      icon: Shield,
      className: 'wireguard',
    }
  }

  if (
    type === 'bridge' ||
    name.includes('bridge')
  ) {
    return {
      label: 'Bridge',
      icon: Network,
      className: 'bridge',
    }
  }

  if (
    type === 'vlan' ||
    name.includes('vlan')
  ) {
    return {
      label: 'VLAN',
      icon: SlidersHorizontal,
      className: 'vlan',
    }
  }

  if (
    type === 'wifi' ||
    name.includes('wlan') ||
    name.includes('wifi')
  ) {
    return {
      label: 'Wireless',
      icon: RadioTower,
      className: 'wireless',
    }
  }

  if (
    type === 'ppp' ||
    name.includes('l2tp') ||
    name.includes('pptp') ||
    name.includes('pppoe') ||
    name.includes('sstp')
  ) {
    return {
      label: 'PPP / VPN',
      icon: Waves,
      className: 'ppp',
    }
  }

  if (
    type === 'tunnel' ||
    name.includes('eoip') ||
    name.includes('gre') ||
    name.includes('ipip')
  ) {
    return {
      label: 'Tunnel',
      icon: Router,
      className: 'tunnel',
    }
  }

  if (
    type === 'ethernet' ||
    name.startsWith('ether') ||
    name.startsWith('sfp')
  ) {
    return {
      label: 'Ethernet',
      icon: EthernetPort,
      className: 'ethernet',
    }
  }

  if (
    name === 'lo' ||
    name.includes('loopback')
  ) {
    return {
      label: 'Loopback',
      icon: Activity,
      className: 'loopback',
    }
  }

  return {
    label:
      item?.if_type &&
      item.if_type !== 'unknown'
        ? item.if_type
        : 'Other',

    icon: Cable,
    className: 'other',
  }
}


function getOperationalStatus(item) {
  if (!item.is_admin_up) {
    return {
      status: 'inactive',
      label: 'معطلة إداريًا',
      className: 'disabled',
      description: 'Admin Down',
    }
  }

  if (item.is_oper_up) {
    return {
      status:
        item.total_bps > 0
          ? 'active'
          : 'online',

      label:
        item.total_bps > 0
          ? 'نشطة'
          : 'تعمل',

      className:
        item.total_bps > 0
          ? 'active'
          : 'online',

      description: 'Operational Up',
    }
  }

  return {
    status: 'offline',
    label: 'متوقفة',
    className: 'offline',
    description: 'Operational Down',
  }
}


function getUtilizationTone(value) {
  if (value === null) {
    return 'unknown'
  }

  if (value >= 90) {
    return 'critical'
  }

  if (value >= 75) {
    return 'warning'
  }

  if (value >= 50) {
    return 'medium'
  }

  return 'normal'
}


function escapeCsvValue(value) {
  const text = String(value ?? '')

  return `"${text.replaceAll(
    '"',
    '""',
  )}"`
}


function SortButton({
  column,
  activeColumn,
  direction,
  onSort,
  children,
}) {
  const active =
    column === activeColumn

  return (
    <button
      type="button"
      className={
        active
          ? 'interfaces-pro-sort active'
          : 'interfaces-pro-sort'
      }
      onClick={() => onSort(column)}
    >
      <span>{children}</span>

      {!active ? (
        <ArrowDownUp size={13} />
      ) : direction === 'asc' ? (
        <ChevronUp size={14} />
      ) : (
        <ChevronDown size={14} />
      )}
    </button>
  )
}


function SummaryCard({
  title,
  value,
  description,
  icon,
  tone = 'primary',
}) {
  const metricTone =
    tone === 'healthy'
      ? 'success'
      : tone === 'warning'
        ? 'warning'
        : tone === 'critical'
          ? 'danger'
          : tone === 'traffic'
            ? 'download'
            : tone === 'purple'
              ? 'purple'
              : tone === 'neutral'
                ? 'neutral'
                : 'primary'

  return (
    <SSMetric
      className={
        [
          'interfaces-pro-summary-card',
          tone,
        ]
          .filter(Boolean)
          .join(' ')
      }
      title={title}
      value={
        value ??
        'غير متوفر'
      }
      description={description}
      icon={icon}
      tone={metricTone}
      size="sm"
      layout="horizontal"
    />
  )
}


function UtilizationBar({
  value,
}) {
  if (
    value === null ||
    value === undefined
  ) {
    return (
      <div className="interface-utilization unavailable">
        <span>غير محسوبة</span>
        <small>لا توجد سرعة Link</small>
      </div>
    )
  }

  const normalizedValue =
    Math.max(
      0,
      Math.min(
        Number(value) || 0,
        100,
      ),
    )

  const utilizationTone =
    getUtilizationTone(
      normalizedValue,
    )

  const progressTone =
    utilizationTone === 'critical'
      ? 'danger'
      : utilizationTone === 'warning'
        ? 'warning'
        : utilizationTone === 'medium'
          ? 'primary'
          : utilizationTone === 'normal'
            ? 'success'
            : 'neutral'

  const toneLabel =
    utilizationTone === 'critical'
      ? 'حرج'
      : utilizationTone === 'warning'
        ? 'مرتفع'
        : utilizationTone === 'medium'
          ? 'متوسط'
          : utilizationTone === 'normal'
            ? 'طبيعي'
            : 'غير معروف'

  return (
    <div className="interface-utilization">
      <SSProgress
        className="interface-utilization-progress"
        label={toneLabel}
        value={normalizedValue}
        tone={progressTone}
        size="sm"
        variant="soft"
        maximumFractionDigits={2}
        animated
      />
    </div>
  )
}


function renderSpeedCell(item) {
  return (
    <div className="interface-pro-speed">
      <strong>
        {formatSpeed(
          item.speed_bps,
        )}
      </strong>

      <small>
        Link Speed
      </small>
    </div>
  )
}


function renderDownloadCell(item) {
  return (
    <span className="interface-pro-rate download">
      <ArrowDown size={14} />

      {formatBitrate(
        item.rx_bps,
      )}
    </span>
  )
}


function renderUploadCell(item) {
  return (
    <span className="interface-pro-rate upload">
      <ArrowUp size={14} />

      {formatBitrate(
        item.tx_bps,
      )}
    </span>
  )
}


function renderUtilizationCell(item) {
  return (
    <UtilizationBar
      value={
        item.utilization_percent
      }
    />
  )
}


function renderErrorsCell(item) {
  return (
    <div
      className={
        item.has_errors
          ? 'interface-pro-errors warning'
          : 'interface-pro-errors healthy'
      }
    >
      {item.has_errors ? (
        <AlertTriangle size={15} />
      ) : (
        <CheckCircle2 size={15} />
      )}

      <div>
        <strong>
          {item.total_errors}
        </strong>

        <small>
          RX
          {' '}
          {item.rx_errors}
          {' '}
          / TX
          {' '}
          {item.tx_errors}
        </small>
      </div>
    </div>
  )
}


function renderMtuCell(item) {
  return (
    <span className="interface-pro-mtu">
      {item.mtu || '--'}
    </span>
  )
}


function renderStatusCell(item) {
  const status =
    getOperationalStatus(item)

  return (
    <div className="interface-pro-status-cell">
      <SSStatusChip
        status={status.status}
        label={status.label}
        size="sm"
        dot
        showIcon={false}
      />

      <small>
        {status.description}
      </small>
    </div>
  )
}


function renderInterfaceCell(item) {
  const presentation =
    getInterfacePresentation(item)

  const Icon =
    presentation.icon

  return (
    <div className="interface-pro-name-cell">
      <div
        className={
          `interface-pro-icon ` +
          `${presentation.className}`
        }
      >
        <Icon size={18} />
      </div>

      <div>
        <strong>
          {item.if_descr}
        </strong>

        <span>
          Index
          {' '}
          #{item.if_index}
        </span>
      </div>
    </div>
  )
}


function renderTypeCell(item) {
  const presentation =
    getInterfacePresentation(item)

  return (
    <span
      className={
        `interface-pro-type ` +
        `${presentation.className}`
      }
    >
      {presentation.label}
    </span>
  )
}


export default function InterfacesTable({
  ip,
  selectedInterface = '',
  onSelectInterface,
  onInterfacesData,
  refreshInterval = 15000,
}) {
  const {
    interfaces,
    summary,
    selectedInterface:
      apiSelectedInterface,
    loading,
    refreshing,
    error,
    lastUpdated,
    refresh,
  } = useInterfaces({
    ip,
    minutes: 15,
    refreshInterval,
  })

  const [
    searchTerm,
    setSearchTerm,
  ] = useState('')

  const [
    statusFilter,
    setStatusFilter,
  ] = useState('all')

  const [
    sortColumn,
    setSortColumn,
  ] = useState('utilization')

  const [
    sortDirection,
    setSortDirection,
  ] = useState('desc')

  useEffect(() => {
    if (
      typeof onInterfacesData !==
      'function'
    ) {
      return
    }

    onInterfacesData({
      interfaces,
      summary,
      loading,
      refreshing,
      error,
      lastUpdated,
    })
  }, [
    error,
    interfaces,
    lastUpdated,
    loading,
    onInterfacesData,
    refreshing,
    summary,
  ])

  const effectiveSelectedInterface =
    selectedInterface ||
    apiSelectedInterface ||
    ''

  const displayedInterfaces =
    useMemo(() => {
      const normalizedSearch =
        searchTerm
          .trim()
          .toLowerCase()

      const filtered =
        interfaces.filter((item) => {
          const matchesSearch =
            !normalizedSearch ||
            item.if_descr
              .toLowerCase()
              .includes(
                normalizedSearch,
              ) ||
            item.if_type
              .toLowerCase()
              .includes(
                normalizedSearch,
              ) ||
            String(item.if_index).includes(
              normalizedSearch,
            )

          if (!matchesSearch) {
            return false
          }

          if (statusFilter === 'up') {
            return item.is_oper_up
          }

          if (statusFilter === 'down') {
            return !item.is_oper_up
          }

          if (
            statusFilter === 'errors'
          ) {
            return item.has_errors
          }

          if (
            statusFilter === 'traffic'
          ) {
            return item.total_bps > 0
          }

          return true
        })

      const sortField =
        SORT_FIELDS[sortColumn] ||
        SORT_FIELDS.utilization

      return [...filtered].sort(
        (first, second) => {
          let firstValue =
            first[sortField]

          let secondValue =
            second[sortField]

          if (
            sortField ===
            'utilization_percent'
          ) {
            firstValue =
              firstValue ?? -1

            secondValue =
              secondValue ?? -1
          }

          let comparison = 0

          if (
            typeof firstValue ===
              'number' &&
            typeof secondValue ===
              'number'
          ) {
            comparison =
              firstValue -
              secondValue
          } else if (
            typeof firstValue ===
              'boolean' &&
            typeof secondValue ===
              'boolean'
          ) {
            comparison =
              Number(firstValue) -
              Number(secondValue)
          } else {
            comparison =
              String(
                firstValue ?? '',
              ).localeCompare(
                String(
                  secondValue ?? '',
                ),
                'ar',
                {
                  numeric: true,
                  sensitivity: 'base',
                },
              )
          }

          return sortDirection ===
            'asc'
            ? comparison
            : -comparison
        },
      )
    }, [
      interfaces,
      searchTerm,
      sortColumn,
      sortDirection,
      statusFilter,
    ])

  function handleSort(column) {
    if (sortColumn === column) {
      setSortDirection(
        (current) =>
          current === 'asc'
            ? 'desc'
            : 'asc',
      )

      return
    }

    setSortColumn(column)

    setSortDirection(
      column === 'interface' ||
        column === 'type' ||
        column === 'index'
        ? 'asc'
        : 'desc',
    )
  }

  function selectInterface(
    interfaceName,
  ) {
    if (
      typeof onSelectInterface ===
      'function'
    ) {
      onSelectInterface(
        interfaceName,
      )
    }
  }

  function exportCsv() {
    if (!displayedInterfaces.length) {
      return
    }

    const header = [
      'Interface',
      'Index',
      'Type',
      'Admin Status',
      'Operational Status',
      'Speed bps',
      'Download bps',
      'Upload bps',
      'Total bps',
      'Utilization Percent',
      'RX Errors',
      'TX Errors',
      'MTU',
      'Last Updated',
    ]

    const rows =
      displayedInterfaces.map(
        (item) => [
          item.if_descr,
          item.if_index,
          item.if_type,
          item.admin_status,
          item.oper_status,
          item.speed_bps,
          item.rx_bps,
          item.tx_bps,
          item.total_bps,
          item.utilization_percent ??
            '',
          item.rx_errors,
          item.tx_errors,
          item.mtu,
          item.last_updated || '',
        ],
      )

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
        type:
          'text/csv;charset=utf-8;',
      },
    )

    const url =
      globalThis.URL.createObjectURL(
        blob,
      )

    const anchor =
      globalThis.document.createElement(
        'a',
      )

    anchor.href = url

    anchor.download =
      `ss4ts-interfaces-${ip || 'device'}.csv`

    globalThis.document.body.appendChild(
      anchor,
    )

    anchor.click()
    anchor.remove()

    globalThis.URL.revokeObjectURL(url)
  }

  return (
    <article className="panel interfaces-pro-panel">
      <div className="interfaces-pro-header">
        <div>
          <p className="eyebrow">
            Enterprise Interfaces
          </p>

          <h3>
            إدارة ومراقبة واجهات الجهاز
          </h3>

          <p className="interfaces-pro-description">
            بيانات التشغيل والسرعة
            والاستخدام والأخطاء من SNMP
            وInfluxDB.
          </p>
        </div>

        <div className="interfaces-pro-header-actions">
          <span className="interfaces-pro-updated">
            آخر تحديث:
            {' '}
            {lastUpdated
              ? formatLastUpdated(
                  lastUpdated,
                )
              : 'بانتظار البيانات'}
          </span>

          <button
            type="button"
            className="interfaces-pro-action"
            onClick={refresh}
            disabled={refreshing}
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

          <button
            type="button"
            className="interfaces-pro-action export"
            onClick={exportCsv}
            disabled={
              !displayedInterfaces.length
            }
          >
            <Download size={16} />
            CSV
          </button>
        </div>
      </div>

      <div className="interfaces-pro-summary-grid">
        <SummaryCard
          title="إجمالي الواجهات"
          value={summary.total}
          description="Total Interfaces"
          icon={Cable}
          tone="total"
        />

        <SummaryCard
          title="تعمل"
          value={
            summary.operational_up
          }
          description="Operational Up"
          icon={CheckCircle2}
          tone="up"
        />

        <SummaryCard
          title="متوقفة"
          value={
            summary.operational_down
          }
          description="Operational Down"
          icon={Unplug}
          tone="down"
        />

        <SummaryCard
          title="تحتوي أخطاء"
          value={summary.with_errors}
          description="Interfaces with errors"
          icon={AlertTriangle}
          tone={
            summary.with_errors > 0
              ? 'errors'
              : 'healthy'
          }
        />

        <SummaryCard
          title="إجمالي Download"
          value={formatBitrate(
            summary.total_rx_bps,
          )}
          description="Aggregate inbound"
          icon={ArrowDown}
          tone="download"
        />

        <SummaryCard
          title="إجمالي Upload"
          value={formatBitrate(
            summary.total_tx_bps,
          )}
          description="Aggregate outbound"
          icon={ArrowUp}
          tone="upload"
        />
      </div>

      <div className="interfaces-pro-toolbar">
        <div className="interfaces-pro-search">
          <Search size={16} />

          <input
            type="search"
            value={searchTerm}
            placeholder="ابحث باسم الواجهة أو النوع أو Index..."
            onChange={(event) =>
              setSearchTerm(
                event.target.value,
              )
            }
          />
        </div>

        <div className="interfaces-pro-filter">
          <SlidersHorizontal
            size={16}
          />

          <select
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(
                event.target.value,
              )
            }
          >
            {FILTER_OPTIONS.map(
              (option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ),
            )}
          </select>
        </div>

        <span className="interfaces-pro-results">
          عرض
          {' '}
          <strong>
            {displayedInterfaces.length}
          </strong>
          {' '}
          من
          {' '}
          <strong>
            {interfaces.length}
          </strong>
        </span>
      </div>

      {error && (
        <div className="interfaces-pro-error">
          <AlertTriangle size={18} />

          <span>{error}</span>

          <button
            type="button"
            onClick={refresh}
          >
            إعادة المحاولة
          </button>
        </div>
      )}

      {loading &&
      !interfaces.length ? (
        <div className="interfaces-pro-state">
          <RefreshCw
            size={28}
            className="is-spinning"
          />

          <strong>
            جارٍ تحميل بيانات الواجهات...
          </strong>
        </div>
      ) : !interfaces.length ? (
        <div className="interfaces-pro-state">
          <CircleOff size={34} />

          <strong>
            لا توجد واجهات متاحة
          </strong>

          <span>
            تأكد من SNMP وإعدادات
            Telegraf لهذا الجهاز.
          </span>
        </div>
      ) : (
        <div className="interfaces-pro-table-wrapper">
          <table className="interfaces-pro-table">
            <thead>
              <tr>
                <th>
                  <SortButton
                    column="status"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    الحالة
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="interface"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    الواجهة
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="type"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    النوع
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="speed"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    السرعة
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="download"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    Download
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="upload"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    Upload
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="utilization"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    الاستخدام
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="errors"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    الأخطاء
                  </SortButton>
                </th>

                <th>
                  <SortButton
                    column="mtu"
                    activeColumn={
                      sortColumn
                    }
                    direction={
                      sortDirection
                    }
                    onSort={handleSort}
                  >
                    MTU
                  </SortButton>
                </th>

                <th>الإجراء</th>
              </tr>
            </thead>

            <tbody>
              {displayedInterfaces.map(
                (item) => {
                  const selected =
                    effectiveSelectedInterface ===
                    item.if_descr

                  return (
                    <tr
                      key={`${item.if_index}-${item.if_descr}`}
                      className={[
                        selected
                          ? 'selected'
                          : '',
                        item.has_errors
                          ? 'has-errors'
                          : '',
                        !item.is_oper_up
                          ? 'is-down'
                          : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      onDoubleClick={() =>
                        selectInterface(
                          item.if_descr,
                        )
                      }
                    >
                      <td>
                        {renderStatusCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderInterfaceCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderTypeCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderSpeedCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderDownloadCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderUploadCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderUtilizationCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderErrorsCell(
                          item,
                        )}
                      </td>

                      <td>
                        {renderMtuCell(
                          item,
                        )}
                      </td>

                      <td>
                        <button
                          type="button"
                          className={
                            selected
                              ? 'interface-pro-select selected'
                              : 'interface-pro-select'
                          }
                          onClick={() =>
                            selectInterface(
                              item.if_descr,
                            )
                          }
                        >
                          <Activity
                            size={15}
                          />

                          {selected
                            ? 'معروض'
                            : 'عرض الرسم'}
                        </button>
                      </td>
                    </tr>
                  )
                },
              )}
            </tbody>
          </table>

          {!displayedInterfaces.length && (
            <div className="interfaces-pro-no-results">
              <Search size={28} />

              <strong>
                لا توجد نتائج مطابقة
              </strong>

              <span>
                غيّر البحث أو عامل التصفية.
              </span>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
