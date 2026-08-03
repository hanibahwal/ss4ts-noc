import {
  Brain,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react'



function decisionConfig(decision) {

  switch(decision) {

    case 'block':
      return {
        label: 'BLOCK',
        icon: ShieldAlert,
      }


    case 'escalate':
      return {
        label: 'ESCALATE',
        icon: AlertTriangle,
      }


    case 'investigate':
      return {
        label: 'INVESTIGATE',
        icon: AlertTriangle,
      }


    default:
      return {
        label: 'MONITOR',
        icon: ShieldCheck,
      }

  }

}



export default function NotificationAuditDecisionCard(
  {
    data,
  }
) {


  if (!data) {

    return (

      <article className="panel">

        <h3>
          Notification AI Decision
        </h3>

        <p>
          No decision available
        </p>

      </article>

    )

  }



  const config =
    decisionConfig(
      data.decision,
    )


  const Icon =
    config.icon



  return (

    <article
      className="panel notification-decision-card"
    >

      <div className="panel-header">

        <div>

          <p className="eyebrow">
            AI Decision Engine
          </p>


          <h3>
            Notification Audit Decision
          </h3>

        </div>


        <Brain
          size={32}
        />

      </div>



      <div className="decision-status">

        <Icon
          size={30}
        />

        <strong>
          {config.label}
        </strong>

      </div>



      <div className="audit-metrics">


        <div>

          <span>
            Confidence
          </span>

          <strong>
            {data.confidence}%
          </strong>

        </div>



        <div>

          <span>
            Risk Score
          </span>

          <strong>
            {data.risk_score}
          </strong>

        </div>



        <div>

          <span>
            Risk Level
          </span>

          <strong>
            {data.risk_level}
          </strong>

        </div>


      </div>



      <div>

        <h4>
          Reason
        </h4>


        <p>
          {data.reason}
        </p>


      </div>



      <div>

        <h4>
          Actions
        </h4>


        {
          data.actions?.map(
            (action,index)=>(
              <p key={index}>
                ✓ {action}
              </p>
            )
          )
        }


      </div>


    </article>

  )

}
