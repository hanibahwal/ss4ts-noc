import {
  forwardRef,
} from 'react'

import './SSProgress.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


function clampPercent(value) {
  const numericValue =
    Number(value)

  if (
    !Number.isFinite(
      numericValue,
    )
  ) {
    return 0
  }

  return Math.max(
    0,
    Math.min(
      numericValue,
      100,
    ),
  )
}


function formatValue(
  value,
  maximumFractionDigits = 1,
) {
  return new Intl.NumberFormat(
    'ar-SA',
    {
      maximumFractionDigits,
    },
  ).format(value)
}


const SSProgress = forwardRef(
  function SSProgress(
    {
      value = 0,
      min = 0,
      max = 100,
      label = '',
      description = '',
      tone = 'primary',
      size = 'md',
      variant = 'default',
      className = '',
      showValue = true,
      valueSuffix = '%',
      maximumFractionDigits = 1,
      striped = false,
      animated = true,
      indeterminate = false,
      marker = null,
      children,
      ...rest
    },
    ref,
  ) {
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

    const normalizedValue =
      Number.isFinite(
        numericValue,
      )
        ? Math.max(
            numericMin,
            Math.min(
              numericValue,
              safeMaximum,
            ),
          )
        : numericMin

    const percentage =
      clampPercent(
        (
          (
            normalizedValue
            - numericMin
          ) /
          (
            safeMaximum
            - numericMin
          )
        )
        * 100,
      )

    const markerPercent =
      marker === null ||
      marker === undefined
        ? null
        : clampPercent(
            (
              (
                Number(marker)
                - numericMin
              ) /
              (
                safeMaximum
                - numericMin
              )
            )
            * 100,
          )

    return (
      <div
        ref={ref}
        className={joinClasses(
          'ss-ui-progress',
          `ss-ui-progress--tone-${tone}`,
          `ss-ui-progress--size-${size}`,
          `ss-ui-progress--variant-${variant}`,
          striped &&
            'ss-ui-progress--striped',
          animated &&
            'ss-ui-progress--animated',
          indeterminate &&
            'ss-ui-progress--indeterminate',
          className,
        )}
        {...rest}
      >
        {label ||
        description ||
        showValue ? (
          <div className="ss-ui-progress__header">
            <div className="ss-ui-progress__heading">
              {label ? (
                <span className="ss-ui-progress__label">
                  {label}
                </span>
              ) : null}

              {description ? (
                <span className="ss-ui-progress__description">
                  {description}
                </span>
              ) : null}
            </div>

            {showValue &&
            !indeterminate ? (
              <strong className="ss-ui-progress__value">
                {formatValue(
                  normalizedValue,
                  maximumFractionDigits,
                )}
                {valueSuffix}
              </strong>
            ) : null}
          </div>
        ) : null}

        <div
          className="ss-ui-progress__track"
          role="progressbar"
          aria-label={
            label ||
            'Progress'
          }
          aria-valuemin={
            numericMin
          }
          aria-valuemax={
            safeMaximum
          }
          aria-valuenow={
            indeterminate
              ? undefined
              : normalizedValue
          }
        >
          <span
            className="ss-ui-progress__fill"
            style={
              indeterminate
                ? undefined
                : {
                    width:
                      `${percentage}%`,
                  }
            }
          />

          {markerPercent !==
          null ? (
            <span
              className="ss-ui-progress__marker"
              style={{
                insetInlineStart:
                  `${markerPercent}%`,
              }}
              title={
                `Threshold: ${marker}`
              }
            />
          ) : null}
        </div>

        {children ? (
          <div className="ss-ui-progress__footer">
            {children}
          </div>
        ) : null}
      </div>
    )
  },
)

export default SSProgress
