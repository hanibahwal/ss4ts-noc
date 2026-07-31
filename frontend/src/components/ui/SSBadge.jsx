import {
  forwardRef,
} from 'react'

import './SSBadge.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


const SSBadge = forwardRef(
  function SSBadge(
    {
      children,
      className = '',
      as: Component = 'span',
      tone = 'neutral',
      variant = 'soft',
      size = 'md',
      icon: Icon = null,
      dot = false,
      pulse = false,
      uppercase = false,
      removable = false,
      onRemove,
      removeLabel = 'إزالة',
      ...rest
    },
    ref,
  ) {
    return (
      <Component
        ref={ref}
        className={joinClasses(
          'ss-ui-badge',
          `ss-ui-badge--tone-${tone}`,
          `ss-ui-badge--variant-${variant}`,
          `ss-ui-badge--size-${size}`,
          dot &&
            'ss-ui-badge--with-dot',
          pulse &&
            'ss-ui-badge--pulse',
          uppercase &&
            'ss-ui-badge--uppercase',
          removable &&
            'ss-ui-badge--removable',
          className,
        )}
        {...rest}
      >
        {dot ? (
          <span
            className="ss-ui-badge__dot"
            aria-hidden="true"
          />
        ) : null}

        {Icon ? (
          <Icon
            className="ss-ui-badge__icon"
            size={14}
            aria-hidden="true"
          />
        ) : null}

        <span className="ss-ui-badge__label">
          {children}
        </span>

        {removable ? (
          <button
            className="ss-ui-badge__remove"
            type="button"
            aria-label={removeLabel}
            onClick={(event) => {
              event.stopPropagation()
              onRemove?.(event)
            }}
          >
            ×
          </button>
        ) : null}
      </Component>
    )
  },
)

export default SSBadge
