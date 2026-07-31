import {
  forwardRef,
} from 'react'

import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
} from 'lucide-react'

import './SSTable.css'


function joinClasses(
  ...classes
) {
  return classes
    .filter(Boolean)
    .join(' ')
}


function getCellValue(
  row,
  column,
) {
  if (
    typeof column.accessor ===
    'function'
  ) {
    return column.accessor(row)
  }

  const accessorKey =
    column.accessorKey ||
    column.key

  return row?.[accessorKey]
}


function TableSkeleton({
  columnCount,
  rowCount = 5,
}) {
  return (
    <tbody>
      {Array.from({
        length: rowCount,
      }).map((_, rowIndex) => (
        <tr
          className="ss-ui-table__skeleton-row"
          key={`skeleton-${rowIndex}`}
        >
          {Array.from({
            length: columnCount,
          }).map((__, columnIndex) => (
            <td
              key={`skeleton-${rowIndex}-${columnIndex}`}
            >
              <span />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}


const SSTable = forwardRef(
  function SSTable(
    {
      columns = [],
      rows = [],
      className = '',
      density = 'normal',
      loading = false,
      error = '',
      emptyTitle = 'لا توجد بيانات',
      emptyDescription = '',
      rowKey = 'id',
      selectedRowKey = null,
      rowClassName = '',
      rowAriaLabel = null,
      onRowClick,
      onRowDoubleClick,
      sortColumn = '',
      sortDirection = 'asc',
      onSort,
      stickyHeader = true,
      striped = false,
      hoverable = true,
      bordered = true,
      loadingRows = 5,
      caption = '',
      ...rest
    },
    ref,
  ) {
    const isInteractive =
      typeof onRowClick ===
        'function' ||
      typeof onRowDoubleClick ===
        'function'

    function resolveRowKey(
      row,
      index,
    ) {
      if (
        typeof rowKey ===
        'function'
      ) {
        return rowKey(
          row,
          index,
        )
      }

      return (
        row?.[rowKey] ??
        index
      )
    }


    function resolveRowClassName(
      row,
      index,
    ) {
      if (
        typeof rowClassName ===
        'function'
      ) {
        return rowClassName(
          row,
          index,
        )
      }

      return rowClassName
    }


    function resolveRowAriaLabel(
      row,
      index,
    ) {
      if (
        typeof rowAriaLabel ===
        'function'
      ) {
        return rowAriaLabel(
          row,
          index,
        )
      }

      return rowAriaLabel
    }

    return (
      <div
        ref={ref}
        className={joinClasses(
          'ss-ui-table-wrap',
          `ss-ui-table-wrap--density-${density}`,
          stickyHeader &&
            'ss-ui-table-wrap--sticky',
          striped &&
            'ss-ui-table-wrap--striped',
          hoverable &&
            'ss-ui-table-wrap--hoverable',
          bordered &&
            'ss-ui-table-wrap--bordered',
          className,
        )}
        {...rest}
      >
        <table className="ss-ui-table">
          {caption ? (
            <caption>
              {caption}
            </caption>
          ) : null}

          <thead>
            <tr>
              {columns.map(
                (column) => {
                  const columnKey =
                    column.key ||
                    column.accessorKey

                  const sortable =
                    column.sortable &&
                    typeof onSort ===
                      'function'

                  const active =
                    sortColumn ===
                    columnKey

                  return (
                    <th
                      key={columnKey}
                      className={joinClasses(
                        column.align &&
                          `ss-ui-table__cell--${column.align}`,
                        column.className,
                      )}
                      style={{
                        width:
                          column.width,
                        minWidth:
                          column.minWidth,
                      }}
                      scope="col"
                    >
                      {sortable ? (
                        <button
                          className={joinClasses(
                            'ss-ui-table__sort',
                            active &&
                              'is-active',
                          )}
                          type="button"
                          onClick={() =>
                            onSort(
                              columnKey,
                            )
                          }
                        >
                          <span>
                            {column.header}
                          </span>

                          {!active ? (
                            <ChevronsUpDown
                              size={13}
                            />
                          ) : sortDirection ===
                            'asc' ? (
                            <ChevronUp
                              size={14}
                            />
                          ) : (
                            <ChevronDown
                              size={14}
                            />
                          )}
                        </button>
                      ) : (
                        column.header
                      )}
                    </th>
                  )
                },
              )}
            </tr>
          </thead>

          {loading ? (
            <TableSkeleton
              columnCount={
                columns.length
              }
              rowCount={
                loadingRows
              }
            />
          ) : error ? (
            <tbody>
              <tr>
                <td
                  className="ss-ui-table__state-cell"
                  colSpan={
                    columns.length
                  }
                >
                  <div className="ss-ui-table__state ss-ui-table__state--error">
                    <strong>
                      تعذر تحميل البيانات
                    </strong>

                    <span>
                      {error}
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          ) : rows.length === 0 ? (
            <tbody>
              <tr>
                <td
                  className="ss-ui-table__state-cell"
                  colSpan={
                    columns.length
                  }
                >
                  <div className="ss-ui-table__state">
                    <strong>
                      {emptyTitle}
                    </strong>

                    {emptyDescription ? (
                      <span>
                        {emptyDescription}
                      </span>
                    ) : null}
                  </div>
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody>
              {rows.map(
                (row, rowIndex) => {
                  const key =
                    resolveRowKey(
                      row,
                      rowIndex,
                    )

                  const selected =
                    selectedRowKey !==
                      null &&
                    selectedRowKey ===
                      key

                  const customRowClassName =
                    resolveRowClassName(
                      row,
                      rowIndex,
                    )

                  const ariaLabel =
                    resolveRowAriaLabel(
                      row,
                      rowIndex,
                    )

                  return (
                    <tr
                      key={key}
                      className={joinClasses(
                        selected &&
                          'is-selected',
                        isInteractive &&
                          'is-interactive',
                        row.className,
                        customRowClassName,
                      )}
                      aria-selected={
                        selected ||
                        undefined
                      }
                      aria-label={
                        ariaLabel ||
                        undefined
                      }
                      tabIndex={
                        isInteractive
                          ? 0
                          : undefined
                      }
                      onClick={() =>
                        onRowClick?.(
                          row,
                          rowIndex,
                        )
                      }
                      onDoubleClick={() =>
                        onRowDoubleClick?.(
                          row,
                          rowIndex,
                        )
                      }
                      onKeyDown={
                        isInteractive
                          ? (event) => {
                              if (
                                event.key ===
                                  'Enter' ||
                                event.key ===
                                  ' '
                              ) {
                                event.preventDefault()

                                onRowClick?.(
                                  row,
                                  rowIndex,
                                )
                              }
                            }
                          : undefined
                      }
                    >
                      {columns.map(
                        (column) => {
                          const columnKey =
                            column.key ||
                            column.accessorKey

                          const value =
                            getCellValue(
                              row,
                              column,
                            )

                          return (
                            <td
                              key={
                                columnKey
                              }
                              className={joinClasses(
                                column.align &&
                                  `ss-ui-table__cell--${column.align}`,
                                column.cellClassName,
                              )}
                            >
                              {typeof column.cell ===
                              'function'
                                ? column.cell({
                                    value,
                                    row,
                                    rowIndex,
                                    column,
                                  })
                                : value ??
                                  '--'}
                            </td>
                          )
                        },
                      )}
                    </tr>
                  )
                },
              )}
            </tbody>
          )}
        </table>
      </div>
    )
  },
)

export default SSTable
