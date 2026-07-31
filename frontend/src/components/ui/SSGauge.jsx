import {
  forwardRef,
  useId,
} from 'react'

import './SSGauge.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


function clamp(
  value,
  min,
  max,
) {
  return Math.max(
    min,
    Math.min(
      value,
      max,
    ),
  )
}


function resolveTone(
  value,
  thresholds,
  fallbackTone,
) {
  if (
    !thresholds ||
    typeof thresholds !==
      'object'
  ) {
    return fallbackTone
  }

  const warning =
    Number(
      thresholds.warning,
    )

  const danger =
    Number(
      thresholds.danger,
    )

  if (
    Number.isFinite(danger) &&
    value >= danger
  ) {
    return 'danger'
  }

  if (
    Number.isFinite(warning) &&
    value >= warning
  ) {
    return 'warning'
  }

  return (
    thresholds.normal ||
    fallbackTone
  )
}


const SSGauge = forwardRef(
  function SSGauge(
    {
      value = 0,
      min = 0,
      max = 100,
      label = '',
      description = '',
      tone = 'primary',
      thresholds = null,
      size = 'md',
      thickness = 10,
      className = '',
      showValue = true,
      valueSuffix = '',
      maximumFractionDigits = 0,
      icon: Icon = null,
      animated = true,
      trackColor = '',
      children,
      ...rest
    },
    ref,
  ) {
    const gradientId =
      useId()
        .replaceAll(
          ':',
          '',
        )

    const numericMin =
      Number(min) || 0

    const numericMax =
      Number(max) || 100

    const safeMaximum =
      numericMax > numericMin
        ? numericMax
        : numericMin + 100

    const numericValue =
      Number(value)

    const safeValue =
      Number.isFinite(
        numericValue,
      )
        ? clamp(
            numericValue,
            numericMin,
            safeMaximum,
          )
        : numericMin

    const percentage =
      clamp(
        (
          (
            safeValue
            - numericMin
          ) /
          (
            safeMaximum
            - numericMin
          )
        )
        * 100,
        0,
        100,
      )

    const effectiveTone =
      resolveTone(
        safeValue,
        thresholds,
        tone,
      )

    const formattedValue =
      new Intl.NumberFormat(
        'ar-SA',
        {
          maximumFractionDigits,
        },
      ).format(
        safeValue,
      )

    return (
      <div
        ref={ref}
        className={joinClasses(
          'ss-ui-gauge',
          `ss-ui-gauge--tone-${effectiveTone}`,
          `ss-ui-gauge--size-${size}`,
          animated &&
            'ss-ui-gauge--animated',
          className,
        )}
        {...rest}
      >
        <div className="ss-ui-gauge__visual">
          <svg
            viewBox="0 0 120 120"
            role="img"
            aria-label={
              label ||
              'Gauge'
            }
          >
            <defs>
              <linearGradient
                id={gradientId}
                x1="0%"
                y1="0%"
                x2="100%"
                y2="100%"
              >
                <stop
                  offset="0%"
                  stopColor="currentColor"
                  stopOpacity="0.52"
                />

                <stop
                  offset="100%"
                  stopColor="currentColor"
                />
              </linearGradient>
            </defs>

            <circle
              className="ss-ui-gauge__track"
              cx="60"
              cy="60"
              r="50"
              style={{
                strokeWidth:
                  thickness,
                stroke:
                  trackColor ||
                  undefined,
              }}
            />

            <circle
              className="ss-ui-gauge__value"
              cx="60"
              cy="60"
              r="50"
              pathLength="100"
              style={{
                strokeWidth:
                  thickness,
                stroke:
                  `url(#${gradientId})`,
                strokeDasharray:
                  `${percentage} 100`,
              }}
            />
          </svg>

          <div className="ss-ui-gauge__center">
            {Icon ? (
              <Icon
                className="ss-ui-gauge__icon"
                aria-hidden="true"
              />
            ) : null}

            {showValue ? (
              <div className="ss-ui-gauge__number">
                <strong>
                  {formattedValue}
                </strong>

                {valueSuffix ? (
                  <span>
                    {valueSuffix}
                  </span>
                ) : null}
              </div>
            ) : null}

            {children}
          </div>
        </div>

        {label ||
        description ? (
          <div className="ss-ui-gauge__caption">
            {label ? (
              <strong>
                {label}
              </strong>
            ) : null}

            {description ? (
              <span>
                {description}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  },
)

export default SSGauge
