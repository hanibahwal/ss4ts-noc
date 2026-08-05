import { useEffect, useState } from "react";

import {
  getNetworkIntelligence,
} from "../services/nocApi";

import AIExecutivePanel from "../components/AIExecutivePanel";

import "./ExecutiveDashboardV2.css";


export default function ExecutiveDashboardV2() {


  const routerIp = "192.168.45.99";


  const [data,setData] = useState(null);


  const [loading,setLoading] = useState(true);



  async function refresh(){

    try {

      const result =
        await getNetworkIntelligence(routerIp);

      setData(result);


    } catch(error){

      console.error(error);

    }


    finally {

      setLoading(false);

    }

  }



  useEffect(()=>{

    refresh();


    const timer =
      setInterval(
        refresh,
        30000
      );


    return ()=>clearInterval(timer);


  },[]);



  if(loading){

    return (

      <div className="noc-loading">

        Loading SS4TS AI Intelligence...

      </div>

    );

  }



  if(!data){

    return (

      <div className="noc-loading">

        No Intelligence Data

      </div>

    );

  }



  const dashboard =
    data.autonomous_dashboard || {};



  const intelligence =
    dashboard.ai_intelligence || {};



  const health =
    dashboard.system_health || {};



  const forecast =
    intelligence.failure_forecast || {};



  const decision =
    data.executive_decision?.decision || {};



  const plan =
    data.response_plan || {};



  return (

<div className="executive-container">


<header className="executive-header">


<h1>
🧠 SS4TS AI Autonomous NOC
</h1>


<p>
Executive Decision Support Center
</p>


</header>



<section className="kpi-grid">


<div className="kpi-card">

<h3>
Network Health
</h3>


<strong>

{health.score || 0}

</strong>


<span>
{health.status}
</span>

</div>



<div className="kpi-card">

<h3>
AI Risk
</h3>


<strong>

{intelligence.risk_level}

</strong>


<span>
Confidence {intelligence.confidence}%
</span>

</div>



<div className="kpi-card">

<h3>
Failure Forecast
</h3>


<strong>

{forecast.failure || "NONE"}

</strong>


<span>

{forecast.probability || 0}%

</span>


</div>



<div className="kpi-card">

<h3>
Automation
</h3>


<strong>

{plan.action_count || 0}

</strong>


<span>

Actions Waiting

</span>

</div>


</section>





<section className="main-panel">


<AIExecutivePanel
decision={decision}
/>


</section>





<section className="remediation-card">


<h2>

⚡ Remediation Workflow

</h2>


<div className="workflow">


<div>

Actions

<br/>

<b>
{plan.action_count}
</b>

</div>



<div>

Status

<br/>

<b>
{plan.status}
</b>

</div>



<div>

Approval

<br/>

<b>

{plan.approval_required
?
"Required"
:
"Automatic"
}

</b>

</div>


</div>



<button>

Open Approval Center

</button>


</section>




</div>


  );

}
