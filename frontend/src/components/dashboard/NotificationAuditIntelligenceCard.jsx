import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react'


function riskConfig(level) {

  switch(level) {

    case 'critical':
      return {
        label: 'CRITICAL',
        icon: ShieldAlert,
        className: 'risk-critical',
      }


    case 'high':
      return {
        label: 'HIGH',
        icon: AlertTriangle,
        className: 'risk-high',
      }


    case 'medium':
      return {
        label: 'MEDIUM',
        icon: ShieldAlert,
        className: 'risk-medium',
      }


    default:
      return {
        label: 'LOW',
        icon: ShieldCheck,
        className: 'risk-low',
      }
  }

}



export default function NotificationAuditIntelligenceCard(
  {
    data,
  }
) {


  if (!data) {

    return (
      <article className="panel">

        <h3>
          Notification Audit Intelligence
        </h3>

        <p>
          No intelligence data available
        </p>

      </article>
    )

  }



  const risk =
    riskConfig(
      data.risk_level
    )


  const RiskIcon =
    risk.icon



  return (

    <article
      className="panel notification-risk-card"
    >


      <div className="panel-header">

        <div>

          <p className="eyebrow">
            AI Security
          </p>


          <h3>
            Notification Audit Intelligence
          </h3>

        </div>


        <RiskIcon
          size={32}
        />

      </div>



      <div
        className={
          `risk-score ${risk.className}`
        }
      >

        <strong>
          {data.risk_score}
        </strong>


        <span>
          {risk.label}
        </span>

      </div>



      <div className="audit-metrics">


        <div>
          <span>
            Total Events
          </span>

          <strong>
            {data.total_events}
          </strong>
        </div>



        <div>

          <span>
            Failed
          </span>

          <strong>
            {data.failed_events}
          </strong>

        </div>



        <div>

          <span>
            Denied
          </span>

          <strong>
            {data.denied_events}
          </strong>

        </div>



        <div>

          <span>
            Success
          </span>

          <strong>
            {data.success_events}
          </strong>

        </div>


      </div>



      <div className="audit-identity">

        <span>
          Top Identity
        </span>


        <strong>
          {data.top_identity || '-'}
        </strong>

      </div>



      <div className="audit-recommendations">

        <h4>
          Recommendations
        </h4>


        {
          data.recommendations?.map(
            (item,index)=>(
              <p key={index}>
                ⚠ {item}
              </p>
            )
          )
        }


      </div>


    </article>

  )

}
