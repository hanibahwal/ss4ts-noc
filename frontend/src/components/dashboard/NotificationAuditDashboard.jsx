import { useEffect, useState } from 'react'
import {
  Activity,
  CheckCircle,
  XCircle,
  ShieldAlert,
} from 'lucide-react'

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

import { api } from '../../services/api'


export default function NotificationAuditDashboard() {

  const [stats, setStats] = useState(null)

  const [timeline, setTimeline] = useState([])

  const [events, setEvents] = useState([])

  const [error, setError] = useState('')


  async function loadAuditData() {

    try {

      setError('')


      const [
        statsResponse,
        timelineResponse,
        searchResponse,
      ] = await Promise.all([

        api.notificationAuditStats(),

        api.notificationAuditTimeline(),

        api.notificationAuditSearch({
          limit: 10,
        }),

      ])


      setStats(
        statsResponse,
      )


      setTimeline(
        timelineResponse.timeline || [],
      )


      setEvents(
        searchResponse.items || [],
      )


    } catch (err) {

      console.error(err)

      setError(
        err.message ||
        'تعذر تحميل تقارير التدقيق',
      )
    }
  }



  useEffect(() => {

    loadAuditData()


    const timer = setInterval(
      loadAuditData,
      60000,
    )


    return () =>
      clearInterval(timer)

  }, [])



  if (error) {

    return (
      <div className="panel error-banner">
        {error}
      </div>
    )
  }



  return (

    <section className="panel wide-panel">

      <div className="panel-header">

        <div>
          <p className="eyebrow">
            Notification Intelligence
          </p>

          <h3>
            Notification Audit Dashboard
          </h3>
        </div>

      </div>



      <div className="stats-grid">


        <AuditCard
          title="Total Events"
          value={stats?.total_events ?? 0}
          icon={Activity}
        />


        <AuditCard
          title="Success"
          value={stats?.success_count ?? 0}
          icon={CheckCircle}
        />


        <AuditCard
          title="Failed"
          value={stats?.failed_count ?? 0}
          icon={XCircle}
        />


        <AuditCard
          title="Denied"
          value={stats?.denied_count ?? 0}
          icon={ShieldAlert}
        />


      </div>




      <div className="panel">

        <h3>
          Audit Timeline
        </h3>


        <ResponsiveContainer
          width="100%"
          height={260}
        >

          <LineChart
            data={timeline}
          >

            <CartesianGrid />


            <XAxis
              dataKey="timestamp"
            />


            <YAxis />


            <Tooltip />


            <Line
              type="monotone"
              dataKey="total"
            />

          </LineChart>

        </ResponsiveContainer>


      </div>





      <div className="panel">

        <h3>
          Latest Audit Events
        </h3>


        <div className="device-list">

          {events.map(
            (event) => (

              <div
                className="device-list-item"
                key={event.audit_id}
              >

                <strong>
                  {event.identity_id}
                </strong>


                <span>
                  {event.action}
                  {' '}
                  -
                  {' '}
                  {event.result}
                </span>


                <small>
                  {event.resource}
                </small>


              </div>

            )
          )}

        </div>


      </div>


    </section>

  )
}




function AuditCard({
  title,
  value,
  icon: Icon,
}) {


  return (

    <div className="panel">

      <Icon size={24}/>

      <p>
        {title}
      </p>

      <h2>
        {value}
      </h2>

    </div>

  )
}
