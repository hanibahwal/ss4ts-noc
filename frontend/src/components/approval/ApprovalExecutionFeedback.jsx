import {
  CheckCircle,
  XCircle,
  ShieldCheck,
  Activity,
  Clock,
} from "lucide-react"



export default function ApprovalExecutionFeedback(
  {
    execution,
  }
) {


  if (!execution) {

    return null

  }



  const action =
    execution.actions?.[0]



  const executionData =
    action?.execution



  const guard =
    action?.guard



  const actionData =
    action?.action





  return (

    <section className="panel">


      <div className="panel-header">


        <div>


          <p className="eyebrow">

            Execution Feedback

          </p>


          <h3>

            Approval Execution Result

          </h3>


        </div>


      </div>






      <div className="stats-grid">


        <FeedbackCard

          icon={Activity}

          title="Action"

          value={
            actionData?.action_type ||
            "-"
          }

        />



        <FeedbackCard

          icon={ShieldCheck}

          title="Guard Status"

          value={
            guard?.status ||
            "-"
          }

        />



        <FeedbackCard

          icon={
            executionData?.executed
              ? CheckCircle
              : XCircle
          }

          title="Execution"

          value={
            executionData?.executed
              ? "Completed"
              : "Failed"
          }

        />



        <FeedbackCard

          icon={Clock}

          title="Time"

          value={
            executionData?.created_at ||
            "-"
          }

        />



      </div>







      <div className="panel">


        <h4>

          Result

        </h4>



        <p>

          {
            executionData?.result ||
            "No execution result"
          }

        </p>



      </div>








      {
        executionData?.execution_id &&


        <div className="panel">


          <h4>

            Execution ID

          </h4>



          <code>

            {
              executionData.execution_id
            }

          </code>


        </div>


      }





    </section>

  )


}







function FeedbackCard(
  {
    icon: Icon,
    title,
    value,
  }
) {


  return (

    <div className="stat-card">


      <Icon size={22}/>



      <div>


        <p>

          {title}

        </p>



        <strong>

          {value}

        </strong>


      </div>


    </div>

  )

}
