import {
  forwardRef,
} from 'react'

import './SSCard.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


const SSCard = forwardRef(
  function SSCard(
    {
      children,
      className = '',
      as: Component = 'article',
      variant = 'default',
      density = 'normal',
      interactive = false,
      selected = false,
      loading = false,
      disabled = false,
      accent = '',
      eyebrow = '',
      title = '',
      description = '',
      icon: Icon = null,
      actions = null,
      footer = null,
      bodyClassName = '',
      headerClassName = '',
      footerClassName = '',
      noBodyPadding = false,
      ...rest
    },
    ref,
  ) {
    const hasHeader = Boolean(
      eyebrow ||
      title ||
      description ||
      Icon ||
      actions,
    )

    return (
      <Component
        ref={ref}
        className={joinClasses(
          'ss-ui-card',
          `ss-ui-card--${variant}`,
          `ss-ui-card--density-${density}`,
          interactive &&
            'ss-ui-card--interactive',
          selected &&
            'ss-ui-card--selected',
          loading &&
            'ss-ui-card--loading',
          disabled &&
            'ss-ui-card--disabled',
          accent &&
            `ss-ui-card--accent-${accent}`,
          className,
        )}
        aria-busy={
          loading || undefined
        }
        aria-disabled={
          disabled || undefined
        }
        {...rest}
      >
        {hasHeader ? (
          <header
            className={joinClasses(
              'ss-ui-card__header',
              headerClassName,
            )}
          >
            <div className="ss-ui-card__heading">
              {Icon ? (
                <span className="ss-ui-card__icon">
                  <Icon
                    size={20}
                    aria-hidden="true"
                  />
                </span>
              ) : null}

              <div className="ss-ui-card__heading-content">
                {eyebrow ? (
                  <span className="ss-ui-card__eyebrow">
                    {eyebrow}
                  </span>
                ) : null}

                {title ? (
                  <h3 className="ss-ui-card__title">
                    {title}
                  </h3>
                ) : null}

                {description ? (
                  <p className="ss-ui-card__description">
                    {description}
                  </p>
                ) : null}
              </div>
            </div>

            {actions ? (
              <div className="ss-ui-card__actions">
                {actions}
              </div>
            ) : null}
          </header>
        ) : null}

        <div
          className={joinClasses(
            'ss-ui-card__body',
            !hasHeader &&
              'ss-ui-card__body--without-header',
            noBodyPadding &&
              'ss-ui-card__body--no-padding',
            bodyClassName,
          )}
        >
          {loading ? (
            <div
              className="ss-ui-card__skeleton"
              aria-label="جارٍ التحميل"
            >
              <span />
              <span />
              <span />
            </div>
          ) : (
            children
          )}
        </div>

        {footer ? (
          <footer
            className={joinClasses(
              'ss-ui-card__footer',
              footerClassName,
            )}
          >
            {footer}
          </footer>
        ) : null}
      </Component>
    )
  },
)

export default SSCard
