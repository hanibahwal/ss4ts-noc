import { useEffect, useState } from "react";

import {
  Activity,
  Brain,
  ShieldAlert,
  Cpu,
  Network,
  CheckCircle,
  AlertTriangle,
  Clock,
} from "lucide-react";

import {
  getNetworkIntelligence,
} from "../services/nocApi";

import "../styles/executive-dashboard.css";


export default function ExecutiveDashboard() {


  const [data,setData] = useState(null);

  const [loading,setLoading] = useState(true);


  const routerIp =
    "192.168.45.99";



  async function loadData(){

    try{

      const result =
        await getNetworkIntelligence(
          routerIp
        );


      setData(result);


    }catch(error){

      console.error(
        error
      );

    }
    finally{

      setLoading(false);

    }

  }



  useEffect(()=>{


    loadData();


    const timer =
      setInterval(
        loadData,
        30000
      );


    return ()=>clearInterval(timer);


  },[]);




  if(loading){

    return (

      <div className="loading">

        Loading AI NOC Intelligence...

      </div>

    );

  }




  const dashboard =
    data?.autonomous_dashboard;



  const decision =
    data?.executive_decision
      ?.decision;



  const response =
    data?.response_plan;




  return (

<div className="executive-dashboard">


<header className="executive-header">


<h1>

<Brain size={38}/>

SS4TS AI Autonomous NOC

</h1>


<p>

Executive Decision Support Center

</p>


</header>





<div className="metric-grid">



<div className="metric-card">

<Activity/>

<h3>

Health Score

</h3>


<div className="metric-number">

{dashboard?.system_health?.score ?? 0}

</div>


<span>

{dashboard?.system_health?.status}

</span>


</div>





<div className="metric-card">


<ShieldAlert/>


<h3>

AI Risk

</h3>


<div className="risk">

{dashboard?.ai_intelligence?.risk_level}

</div>


<p>

Confidence:

{dashboard?.ai_intelligence?.confidence}%

</p>


</div>





<div className="metric-card">


<Cpu/>


<h3>

Failure Forecast

</h3>


<div>

{
dashboard
?.ai_intelligence
?.failure_forecast
?.failure
}

</div>


<p>

Probability:

{
dashboard
?.ai_intelligence
?.failure_forecast
?.probability
}%

</p>


</div>




</div>







<div className="content-grid">



<div className="card">


<h2>

<Brain/>

AI Executive Decision

</h2>



<div className="decision">


{decision || "No Decision"}


</div>


<p>

Priority:

<strong>

{
data
?.executive_decision
?.decision
?.priority

}

</strong>

</p>



<p>

{
data
?.executive_decision
?.decision
?.reasoning

}

</p>



</div>






<div className="card">


<h2>

<Network/>

Remediation Workflow

</h2>



<div className="workflow">


<div>

<Clock/>

Status:

{response?.status}

</div>


<div>

Actions:

{response?.action_count}

</div>



</div>



{
response?.actions?.map(
(action,index)=>(


<div
className="action"
key={index}
>


<CheckCircle/>


<div>


<strong>

{action.action_type}

</strong>


<p>

{action.description}

</p>


</div>


</div>


)

)

}



<button>

Open Approval Center

</button>



</div>



</div>






<div className="summary-card">


<AlertTriangle/>


<p>

{
dashboard?.summary
}

</p>


</div>




</div>


  );

}
