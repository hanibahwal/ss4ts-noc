import {
  SSMetric,
} from '../ui'


const TONE_MAP = {
  blue: 'primary',
  green: 'success',
  red: 'danger',
  orange: 'warning',
  purple: 'purple',
  download: 'download',
  upload: 'upload',
  neutral: 'neutral',
}


export default function StatCard({
  title,
  value,
  description,
  icon,
  tone = 'blue',
  loading = false,
  interactive = false,
  selected = false,
  className = '',
  onClick,
}) {
  const metricTone =
    TONE_MAP[tone] ||
    'primary'

  return (
    <SSMetric
      className={
        [
          'stat-card',
          `tone-${tone}`,
          className,
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
      size="md"
      layout="horizontal"
      loading={loading}
      interactive={
        interactive ||
        typeof onClick ===
          'function'
      }
      selected={selected}
      onClick={onClick}
    />
  )
}
