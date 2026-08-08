import {
  Activity,
  Radar,
  Square,
} from 'lucide-react'

import {
  useEffect,
  useState,
} from 'react'

import { api } from '../../services/api'

import './NetworkDiscoveryPanel.css'


const TERMINAL_STATES = new Set([
  'COMPLETED',
  'FAILED',
  'CANCELLED',
])


export default function NetworkDiscoveryPanel() {

  const [networkRange, setNetworkRange] =
    useState('')

  const [job, setJob] =
    useState(null)

  const [devices, setDevices] =
    useState([])

  const [error, setError] =
    useState('')

  const [starting, setStarting] =
    useState(false)


  const running =
    job?.status === 'RUNNING'


  async function refreshJob(jobId) {

    const [
      currentJob,
      currentDevices,
    ] = await Promise.all([
      api.discoveryStatus(jobId),
      api.discoveryDevices(jobId),
    ])

    setJob(currentJob)

    setDevices(
      currentDevices.devices || []
    )
  }


  useEffect(() => {

    if (
      !job?.job_id ||
      TERMINAL_STATES.has(job.status)
    ) {
      return
    }

    const timer =
      window.setInterval(
        () => {
          refreshJob(job.job_id)
            .catch((currentError) => {
              setError(
                currentError.message ||
                'تعذر تحديث حالة الفحص'
              )
            })
        },
        1000,
      )

    return () =>
      window.clearInterval(timer)

  }, [
    job?.job_id,
    job?.status,
  ])


  async function startScan(event) {

    event.preventDefault()

    const value =
      networkRange.trim()

    if (!value) {
      setError(
        'أدخل Network Range مثل 192.168.13.0/22'
      )
      return
    }

    setStarting(true)
    setError('')
    setDevices([])

    try {

      const created =
        await api.discoveryStart(value)

      setJob(created)

    } catch (currentError) {

      setError(
        currentError.message ||
        'تعذر بدء فحص الشبكة'
      )

    } finally {

      setStarting(false)

    }
  }


  async function cancelScan() {

    if (!job?.job_id)
      return

    try {

      const result =
        await api.discoveryCancel(
          job.job_id
        )

      setJob(result)

    } catch (currentError) {

      setError(
        currentError.message ||
        'تعذر إلغاء الفحص'
      )

    }
  }


  return (
    <section className="network-discovery-panel">

      <div className="network-discovery-header">

        <div>
          <span className="network-discovery-kicker">
            SS4TS Autonomous Discovery
          </span>

          <h2>
            اكتشاف الشبكة
          </h2>

          <p>
            أدخل نطاق CIDR وسيقوم النظام
            باكتشاف الأجهزة الحية تلقائيًا.
          </p>
        </div>

        <div className="network-discovery-status">
          <Activity size={16} />

          {
            running
              ? 'جارٍ الفحص'
              : job?.status === 'COMPLETED'
                ? 'اكتمل الفحص'
                : 'جاهز'
          }
        </div>

      </div>


      <form
        className="network-discovery-form"
        onSubmit={startScan}
      >

        <input
          type="text"
          dir="ltr"
          value={networkRange}
          onChange={
            event =>
              setNetworkRange(
                event.target.value
              )
          }
          placeholder="192.168.13.0/22"
          disabled={running || starting}
        />

        <button
          type="submit"
          disabled={running || starting}
        >
          <Radar size={18} />

          {
            running
              ? 'جارٍ الفحص'
              : 'فحص الشبكة'
          }
        </button>

        {
          running && (
            <button
              type="button"
              className="cancel"
              onClick={cancelScan}
            >
              <Square size={16} />
              إلغاء
            </button>
          )
        }

      </form>


      {
        error && (
          <div className="network-discovery-error">
            {error}
          </div>
        )
      }


      {
        job && (
          <>

            <div className="network-discovery-info">

              <span>
                الرنج الفعلي:
                <strong dir="ltr">
                  {job.normalized_range}
                </strong>
              </span>

              <span>
                تم الفحص:
                <strong>
                  {job.scanned} / {job.total_hosts}
                </strong>
              </span>

              <span>
                الأجهزة الحية:
                <strong>
                  {job.found}
                </strong>
              </span>

            </div>


            <div className="network-discovery-progress">

              <div
                style={{
                  width:
                    `${Math.min(
                      100,
                      Number(job.progress || 0)
                    )}%`,
                }}
              />

            </div>


            <div className="network-discovery-summary">

              <article>
                <span>MikroTik</span>
                <strong>{job.mikrotik}</strong>
              </article>

              <article>
                <span>Ubiquiti</span>
                <strong>{job.ubiquiti}</strong>
              </article>

              <article>
                <span>أخرى</span>
                <strong>{job.other}</strong>
              </article>

              <article>
                <span>المجموع</span>
                <strong>{job.found}</strong>
              </article>

            </div>


            {
              devices.length > 0 && (
                <div className="network-discovery-devices">

                  <h3>
                    الأجهزة المكتشفة
                  </h3>

                  <table>

                    <thead>
                      <tr>
                        <th>IP</th>
                        <th>Vendor</th>
                        <th>النوع</th>
                        <th>Ports</th>
                        <th>Confidence</th>
                      </tr>
                    </thead>

                    <tbody>

                      {
                        devices
                          .slice(0, 100)
                          .map(
                            device => (
                              <tr
                                key={
                                  device.ip_address
                                }
                              >
                                <td dir="ltr">
                                  {
                                    device.ip_address
                                  }
                                </td>

                                <td>
                                  {
                                    device.vendor ||
                                    'Unknown'
                                  }
                                </td>

                                <td>
                                  {
                                    device.device_type ||
                                    'Network Device'
                                  }
                                </td>

                                <td dir="ltr">
                                  {
                                    (
                                      device.open_ports ||
                                      []
                                    ).join(', ') ||
                                    '—'
                                  }
                                </td>

                                <td>
                                  {
                                    device.confidence ||
                                    0
                                  }%
                                </td>
                              </tr>
                            )
                          )
                      }

                    </tbody>

                  </table>

                </div>
              )
            }

          </>
        )
      }

    </section>
  )
}
