import React from "react";


export default function RemediationApprovalPanel({
  responsePlan
}) {


  if (!responsePlan) {

    return (

      <div className="ai-card empty">

        <h3>
          🛡️ Remediation Approval
        </h3>

        <p>
          No remediation plan available
        </p>

      </div>

    );

  }



  return (

    <div className="ai-card remediation-card">


      <div className="ai-header">


        <h2>
          🛡️ Human Approval Workflow
        </h2>


        <span className="warning">

          {responsePlan.status}

        </span>


      </div>




      <div className="ai-decision">


        <h1>

          {responsePlan.decision}

        </h1>


        <p>

          Priority:
          {" "}
          <strong>
            {responsePlan.priority}
          </strong>

        </p>


      </div>




      <div className="ai-section">


        <h3>
          Recommended Actions
        </h3>



        <ul>


          {
            responsePlan.actions?.map(
              (action, index) => (


                <li key={index}>


                  <strong>
                    {action.action_type}
                  </strong>


                  <br />


                  {action.description}


                  <br />


                  <small>

                    Risk:
                    {" "}
                    {action.risk_level}

                  </small>


                </li>


              )

            )
          }


        </ul>


      </div>





      <div className="approval-box">


        <h3>

          👤 Approval Required

        </h3>


        <p>

          AI has prepared the remediation plan.
          Human approval is required before execution.

        </p>



        <div className="approval-actions">


          <button className="approve-button">

            ✅ APPROVE & EXECUTE

          </button>



          <button className="reject-button">

            ❌ REJECT

          </button>


        </div>


      </div>



    </div>

  );


}
