import {
  forwardRef,
} from 'react'

import SSProgress from './SSProgress'

import './SSMetric.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


function formatMetricValue(
  value,
  maximumFractionDigits = 2,
) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return 'غير متوفر'
  }

  if (
    typeof value === 'number' &&
    Number.isFinite(value)
  ) {
    return new Intl.NumberFormat(
      'ar-SA',
      {
        maximumFractionDigits,
      },
    ).format(value)
  }

  return String(value)
}


const SSMetric = forwardRef(
  function SSMetric(
    {
      title,
      value,
      description = '',
      unit = '',
      icon: Icon = null,
      tone = 'primary',
      size = 'md',
      layout = 'horizontal',
      className = '',
      trend = null,
      trendLabel = '',
      progress = null,
      progressMax = 100,
      loading = false,
      interactive = false,
      selected = false,
      onClick,
      maximumFractionDigits = 2,
      children,
      ...rest
    },
    ref,
  ) {
    const formattedValue =
      formatMetricValue(
        value,
        maximumFractionDigits,
      )

    const numericTrend =
      Number(trend)

    const hasTrend =
      trend !== null &&
      trend !== undefined &&
      Number.isFinite(
        numericTrend,
      )

    const trendDirection =
      numericTrend > 0
        ? 'up'
        : numericTrend < 0
          ? 'down'
          : 'flat'

    const isInteractive =
      interactive ||
      typeof onClick === 'function'

    return (
      <article
        ref={ref}
        className={joinClasses(
          'ss-ui-metric',
          `ss-ui-metric--tone-${tone}`,
          `ss-ui-metric--size-${size}`,
          `ss-ui-metric--layout-${layout}`,
          loading &&
            'ss-ui-metric--loading',
          isInteractive &&
            'ss-ui-metric--interactive',
          selected &&
            'ss-ui-metric--selected',
          className,
        )}
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
        aria-busy={
          loading || undefined
        }
        {...rest}
      >
        {loading ? (
          <div className="ss-ui-metric__skeleton">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <>
            {Icon ? (
              <div className="ss-ui-metric__icon">
                <Icon
                  size={20}
                  aria-hidden="true"
                />
              </div>
            ) : null}

            <div className="ss-ui-metric__content">
              <div className="ss-ui-metric__header">
                <span className="ss-ui-metric__title">
                  {title}
                </span>

                {hasTrend ? (
                  <span
                    className={joinClasses(
                      'ss-ui-metric__trend',
                      `ss-ui-metric__trend--${trendDirection}`,
                    )}
                  >
                    {numericTrend > 0
                      ? '↑'
                      : numericTrend < 0
                        ? '↓'
                        : '–'}

                    {Math.abs(
                      numericTrend,
                    )}

                    {trendLabel}
                  </span>
                ) : null}
              </div>

              <div className="ss-ui-metric__value">
                <strong>
                  {formattedValue}
                </strong>

                {unit ? (
                  <span>{unit}</span>
                ) : null}
              </div>

              {description ? (
                <p className="ss-ui-metric__description">
                  {description}
                </p>
              ) : null}

              {progress !== null &&
              progress !== undefined ? (
                <SSProgress
                  className="ss-ui-metric__progress"
                  value={progress}
                  max={progressMax}
                  tone={tone}
                  size="xs"
                  variant="soft"
                  showValue={false}
                />
              ) : null}

              {children ? (
                <div className="ss-ui-metric__footer">
                  {children}
                </div>
              ) : null}
            </div>
          </>
        )}
      </article>
    )
  },
)

export default SSMetric
