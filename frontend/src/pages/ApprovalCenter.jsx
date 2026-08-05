import {
  CheckCircle,
  XCircle,
  ShieldCheck,
  Clock,
  Server,
} from "lucide-react";


import "../styles/executive-dashboard.css";



export default function ApprovalCenter(){


return (

<div className="executive-dashboard">



<header className="executive-header">


<h1>

<ShieldCheck size={40}/>

Human Approval Center

</h1>


<p>

SS4TS AI Remediation Authorization Workflow

</p>


</header>






<div className="content-grid">



<div className="card">


<h2>

<Clock/>

Pending Approvals

</h2>



<div className="action">


<Server/>


<div>


<strong>

OPTIMIZE_CPU_LOAD

</strong>


<p>

Router:
192.168.45.99

</p>


<p>

Priority:
CRITICAL

</p>


</div>


</div>





<div className="action">


<div>


<strong>

Actions

</strong>


<p>

✓ Check CPU Process

</p>


<p>

✓ Check Firewall Load

</p>


<p>

✓ Analyze Traffic Load

</p>


</div>


</div>





<div className="workflow-buttons">


<button
className="approve"
>


<CheckCircle/>

Approve


</button>



<button
className="reject"
>


<XCircle/>

Reject


</button>


</div>




</div>




<div className="card">


<h2>

AI Safety Policy

</h2>


<p>

✓ Human approval required

</p>


<p>

✓ Backup before execution

</p>


<p>

✓ Rollback available

</p>


<p>

✓ Full audit logging

</p>



</div>



</div>



</div>


);


}
