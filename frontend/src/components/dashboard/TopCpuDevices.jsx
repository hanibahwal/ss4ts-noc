import { Cpu } from 'lucide-react'

export default function TopCpuDevices({ devices }) {
  const maximum = Math.max(
    100,
    ...devices.map((device) => Number(device.cpu || 0)),
  )

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Top CPU Devices</p>
          <h3>أعلى الأجهزة استهلاكًا</h3>
        </div>

        <Cpu size={22} />
      </div>

      <div className="top-cpu-list">
        {devices.length > 0 ? (
          devices.slice(0, 5).map((device, index) => (
            <div className="cpu-device-row" key={device.ip}>
              <span className="cpu-rank">{index + 1}</span>

              <div className="cpu-device-info">
                <div>
                  <strong>{device.name}</strong>
                  <span>{device.ip}</span>
                </div>

                <div className="cpu-progress-track">
                  <div
                    className={`cpu-progress ${
                      device.cpu >= 90
                        ? 'critical'
                        : device.cpu >= 70
                          ? 'warning'
                          : ''
                    }`}
                    style={{
                      width: `${Math.min(
                        100,
                        (Number(device.cpu || 0) / maximum) * 100,
                      )}%`,
                    }}
                  />
                </div>
              </div>

              <strong className="cpu-value">{device.cpu}%</strong>
            </div>
          ))
        ) : (
          <div className="events-empty">
            <Cpu size={36} />
            <strong>لا توجد بيانات CPU</strong>
          </div>
        )}
      </div>
    </article>
  )
}
