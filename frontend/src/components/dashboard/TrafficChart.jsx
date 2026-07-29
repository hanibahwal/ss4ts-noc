import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Activity } from 'lucide-react'
import { formatBitrate } from '../../utils/formatters'

export default function TrafficChart({ data }) {
  return (
    <article className="panel traffic-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Live Traffic</p>
          <h3>حركة الشبكة الحية</h3>
        </div>

        <Activity size={22} />
      </div>

      <div className="traffic-summary">
        <div>
          <span>Download الحالي</span>
          <strong>
            {formatBitrate(data.at(-1)?.rx_bps)}
          </strong>
        </div>

        <div>
          <span>Upload الحالي</span>
          <strong>
            {formatBitrate(data.at(-1)?.tx_bps)}
          </strong>
        </div>
      </div>

      <div className="traffic-chart-container">
        {data.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 15, right: 5, left: 5, bottom: 0 }}
            >
              <defs>
                <linearGradient id="rxFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="#3788ff"
                    stopOpacity={0.35}
                  />
                  <stop
                    offset="95%"
                    stopColor="#3788ff"
                    stopOpacity={0}
                  />
                </linearGradient>

                <linearGradient id="txFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="#38d5a5"
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="95%"
                    stopColor="#38d5a5"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>

              <CartesianGrid
                stroke="rgba(255,255,255,0.055)"
                vertical={false}
              />

              <XAxis
                dataKey="time"
                stroke="#617791"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />

              <YAxis
                stroke="#617791"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={72}
                tickFormatter={formatBitrate}
              />

              <Tooltip
                contentStyle={{
                  background: '#101f33',
                  border: '1px solid rgba(255,255,255,.1)',
                  borderRadius: '12px',
                  color: '#fff',
                }}
                formatter={(value, name) => [
                  formatBitrate(value),
                  name === 'rx_bps' ? 'Download' : 'Upload',
                ]}
              />

              <Legend
                formatter={(value) =>
                  value === 'rx_bps' ? 'Download' : 'Upload'
                }
              />

              <Area
                type="monotone"
                dataKey="rx_bps"
                stroke="#3788ff"
                strokeWidth={2}
                fill="url(#rxFill)"
                isAnimationActive={false}
              />

              <Area
                type="monotone"
                dataKey="tx_bps"
                stroke="#38d5a5"
                strokeWidth={2}
                fill="url(#txFill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart-empty">
            <Activity size={35} />
            <strong>جاري جمع بيانات Traffic</strong>
            <span>
              سيظهر الرسم بعد وصول عينتين من البيانات.
            </span>
          </div>
        )}
      </div>
    </article>
  )
}
