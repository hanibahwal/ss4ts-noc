import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Cable,
  CheckCircle2,
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
  SSTable,
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


function renderActionCell({
  item,
  selected,
  onSelect,
}) {
  return (
    <button
      type="button"
      className={
        selected
          ? 'interface-pro-select selected'
          : 'interface-pro-select'
      }
      onClick={(event) => {
        event.stopPropagation()

        onSelect(
          item.if_descr,
        )
      }}
      aria-pressed={selected}
      aria-label={
        selected
          ? `الواجهة ${item.if_descr} معروضة حاليًا`
          : `عرض الرسم البياني للواجهة ${item.if_descr}`
      }
    >
      <Activity size={15} />

      {selected
        ? 'معروض'
        : 'عرض الرسم'}
    </button>
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


function createInterfaceColumns({
  selectInterface,
  effectiveSelectedInterface,
}) {
  return [
    {
      key: 'status',
      header: 'الحالة',
      sortable: true,
      minWidth: 150,
      cell: ({ row }) =>
        renderStatusCell(row),
    },
    {
      key: 'interface',
      header: 'الواجهة',
      sortable: true,
      minWidth: 200,
      cell: ({ row }) =>
        renderInterfaceCell(row),
    },
    {
      key: 'type',
      header: 'النوع',
      sortable: true,
      minWidth: 120,
      cell: ({ row }) =>
        renderTypeCell(row),
    },
    {
      key: 'speed',
      header: 'السرعة',
      sortable: true,
      minWidth: 130,
      cell: ({ row }) =>
        renderSpeedCell(row),
    },
    {
      key: 'download',
      header: 'Download',
      sortable: true,
      minWidth: 130,
      cell: ({ row }) =>
        renderDownloadCell(row),
    },
    {
      key: 'upload',
      header: 'Upload',
      sortable: true,
      minWidth: 130,
      cell: ({ row }) =>
        renderUploadCell(row),
    },
    {
      key: 'utilization',
      header: 'الاستخدام',
      sortable: true,
      minWidth: 180,
      cell: ({ row }) =>
        renderUtilizationCell(row),
    },
    {
      key: 'errors',
      header: 'الأخطاء',
      sortable: true,
      minWidth: 150,
      cell: ({ row }) =>
        renderErrorsCell(row),
    },
    {
      key: 'mtu',
      header: 'MTU',
      sortable: true,
      minWidth: 90,
      cell: ({ row }) =>
        renderMtuCell(row),
    },
    {
      key: 'action',
      header: 'الإجراء',
      sortable: false,
      minWidth: 120,
      cell: ({ row }) =>
        renderActionCell({
          item: row,
          selected:
            effectiveSelectedInterface ===
            row.if_descr,
          onSelect:
            selectInterface,
        }),
    },
  ]
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
  const interfaceColumns =
    createInterfaceColumns({
      selectInterface,
      effectiveSelectedInterface,
    })
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
          <SSTable
            columns={interfaceColumns}
            rows={displayedInterfaces}
            rowKey={(row) =>
              row.if_descr
            }
            selectedRowKey={
              effectiveSelectedInterface
            }
            sortColumn={sortColumn}
            sortDirection={sortDirection}
            onSort={handleSort}
            onRowDoubleClick={(row) =>
              selectInterface(
                row.if_descr,
              )
            }
            rowClassName={(row) =>
              [
                row.has_errors
                  ? 'has-errors'
                  : '',
                !row.is_oper_up
                  ? 'is-down'
                  : '',
              ]
                .filter(Boolean)
                .join(' ')
            }
            rowAriaLabel={(row) =>
              `واجهة ${row.if_descr}`
            }
            density="compact"
            stickyHeader
            striped
            hoverable
            bordered
            emptyTitle="لا توجد نتائج مطابقة"
            emptyDescription="غيّر البحث أو الفلتر لعرض واجهات أخرى."
          />
        </div>
      )}
    </article>
  )
}
