import { useState } from "react"


export default function ApprovalActions({
  approval,
  onApproved,
  onRejected,
}) {


  const [loading, setLoading] = useState(false)


  if (!approval) {

    return (

      <div className="panel">

        Select approval request

      </div>

    )

  }



  async function approve() {


    setLoading(true)


    try {


      const response = await fetch(

        `/api/v1/notifications/audit/response/approval/${approval.approval_id}/approve`,

        {
          method:
            "POST",
        }

      )


      const data =
        await response.json()



      if (onApproved) {

        onApproved(data)

      }


    }

    finally {

      setLoading(false)

    }

  }





  async function reject() {


    setLoading(true)


    try {


      const response = await fetch(

        `/api/v1/notifications/audit/response/approval/${approval.approval_id}/reject`,

        {
          method:
            "POST",
        }

      )


      const data =
        await response.json()



      if (onRejected) {

        onRejected(data)

      }


    }

    finally {

      setLoading(false)

    }

  }





  return (

    <div className="panel">


      <h3>

        Approval Actions

      </h3>



      <p>

        Action:

        {" "}

        {approval.action_type}

      </p>



      <p>

        Status:

        {" "}

        {approval.status}

      </p>



      <button

        disabled={loading}

        onClick={approve}

      >

        ✅ Approve

      </button>



      <button

        disabled={loading}

        onClick={reject}

      >

        ❌ Reject

      </button>



    </div>

  )

}
