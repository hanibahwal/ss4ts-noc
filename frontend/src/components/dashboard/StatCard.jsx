import SSCard from '../ui/SSCard'


const TONE_ACCENT_MAP = {
  blue: 'primary',
  green: 'success',
  red: 'danger',
  orange: 'warning',
  purple: 'purple',
  download: 'download',
  upload: 'upload',
}


export default function StatCard({
  title,
  value,
  description,
  icon: Icon,
  tone = 'blue',
  loading = false,
  interactive = false,
  selected = false,
  className = '',
  onClick,
}) {
  const accent =
    TONE_ACCENT_MAP[tone] ||
    'primary'

  const isInteractive =
    interactive ||
    typeof onClick === 'function'

  return (
    <SSCard
      as="article"
      className={
        [
          'stat-card',
          `tone-${tone}`,
          className,
        ]
          .filter(Boolean)
          .join(' ')
      }
      variant="default"
      density="compact"
      accent={accent}
      loading={loading}
      interactive={isInteractive}
      selected={selected}
      noBodyPadding
      bodyClassName="stat-card-layout"
      onClick={onClick}
      role={
        isInteractive
          ? 'button'
          : undefined
      }
      tabIndex={
        isInteractive
          ? 0
          : undefined
      }
      onKeyDown={
        isInteractive
          ? (event) => {
              if (
                event.key === 'Enter' ||
                event.key === ' '
              ) {
                event.preventDefault()

                onClick?.(event)
              }
            }
          : undefined
      }
    >
      <div className="stat-icon">
        {Icon ? (
          <Icon
            size={23}
            aria-hidden="true"
          />
        ) : null}
      </div>

      <div className="stat-card-content">
        <span>{title}</span>

        <strong>
          {value ??
            'غير متوفر'}
        </strong>

        {description ? (
          <small>
            {description}
          </small>
        ) : null}
      </div>
    </SSCard>
  )
}
