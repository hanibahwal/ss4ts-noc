import { Clock3, RefreshCw, Search, X } from 'lucide-react'

export default function Header({
  title,
  subtitle,
  onRefresh,
  refreshing = false,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'ابحث عن جهاز أو موقع أو IP...',
  lastUpdated,
}) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">SS4TS Network Operations Center</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>

        {lastUpdated && (
          <div className="last-updated">
            <Clock3 size={14} />
            آخر تحديث:
            <strong>{lastUpdated.toLocaleTimeString('ar-SA')}</strong>
          </div>
        )}
      </div>

      <div className="topbar-actions">
        {typeof onSearchChange === 'function' && (
          <label className="global-search">
            <Search size={18} />

            <input
              type="search"
              value={searchValue}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
            />

            {searchValue && (
              <button
                type="button"
                className="clear-search"
                onClick={() => onSearchChange('')}
                title="مسح البحث"
              >
                <X size={15} />
              </button>
            )}
          </label>
        )}

        {typeof onRefresh === 'function' && (
          <button
            type="button"
            className="refresh-button"
            onClick={onRefresh}
            disabled={refreshing}
          >
            <RefreshCw
              size={18}
              className={refreshing ? 'spin' : ''}
            />
            {refreshing ? 'جاري التحديث' : 'تحديث'}
          </button>
        )}
      </div>
    </header>
  )
}
