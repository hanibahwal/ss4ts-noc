import React from "react";


export default function AIExecutivePanel({
  executiveDecision
}) {


  if (!executiveDecision) {

    return (
      <div className="ai-card empty">
        <h3>
          🤖 AI Executive Decision
        </h3>

        <p>
          No decision available
        </p>

      </div>
    );

  }


  const decision =
    executiveDecision.decision || {};


  return (

    <div className="ai-card">


      <div className="ai-header">

        <h2>
          🤖 AI Executive Decision
        </h2>

        <span className={
          decision.priority === "CRITICAL"
          ? "critical"
          : "warning"
        }>
          {decision.priority}
        </span>

      </div>



      <div className="ai-decision">

        <h1>
          {decision.decision}
        </h1>

      </div>



      <div className="ai-grid">


        <div className="ai-stat">

          <label>
            Confidence
          </label>

          <strong>
            {decision.confidence_percent}%
          </strong>

        </div>



        <div className="ai-stat">

          <label>
            Forecast Probability
          </label>

          <strong>
            {decision.forecast_probability_percent}%
          </strong>

        </div>



        <div className="ai-stat">

          <label>
            Approval
          </label>

          <strong>
            {
              decision.approval_required
              ? "Required"
              : "Automatic"
            }
          </strong>

        </div>


      </div>



      <div className="ai-section">

        <h3>
          Business Impact
        </h3>


        <p>
          {decision.business_impact}
        </p>


      </div>




      <div className="ai-section">

        <h3>
          🧠 AI Reasoning
        </h3>


        <p>
          {decision.reasoning}
        </p>


      </div>




      <div className="ai-section">

        <h3>
          Recommended Actions
        </h3>


        <ul>

          {
            decision.recommended_actions?.map(
              (action,index)=>(

                <li key={index}>
                  ✅ {action}
                </li>

              )
            )
          }

        </ul>


      </div>




      {
        decision.approval_required &&

        <button
          className="approval-button"
        >

          👤 Human Approval Required

        </button>

      }



    </div>

  );

}
