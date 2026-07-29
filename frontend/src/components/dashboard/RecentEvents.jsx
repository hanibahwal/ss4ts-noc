import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Info,
  Thermometer,
  WifiOff,
} from 'lucide-react'

const typeConfig = {
  offline: {
    icon: WifiOff,
    label: 'انقطاع',
    className: 'critical',
  },
  recovered: {
    icon: CheckCircle2,
    label: 'استعادة',
    className: 'success',
  },
  cpu: {
    icon: Cpu,
    label: 'CPU',
    className: 'warning',
  },
  temperature: {
    icon: Thermometer,
    label: 'حرارة',
    className: 'warning',
  },
  info: {
    icon: Info,
    label: 'معلومة',
    className: 'info',
  },
}

export default function RecentEvents({ events }) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Recent Events</p>
          <h3>أحدث الأحداث</h3>
        </div>

        <AlertTriangle size={22} />
      </div>

      <div className="events-list">
        {events.length > 0 ? (
          events.slice(0, 8).map((event) => {
            const config = typeConfig[event.type] || typeConfig.info
            const Icon = config.icon

            return (
              <div
                className={`event-item event-${config.className}`}
                key={event.id}
              >
                <div className="event-icon">
                  <Icon size={18} />
                </div>

                <div className="event-content">
                  <div>
                    <strong>{event.title}</strong>
                    <span className="event-type">{config.label}</span>
                  </div>

                  <p>{event.message}</p>
                </div>

                <time>{event.time}</time>
              </div>
            )
          })
        ) : (
          <div className="events-empty">
            <CheckCircle2 size={38} />
            <strong>لا توجد أحداث حرجة</strong>
            <span>الشبكة تعمل بصورة طبيعية.</span>
          </div>
        )}
      </div>
    </article>
  )
}
