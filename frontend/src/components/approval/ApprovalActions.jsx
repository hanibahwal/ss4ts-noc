import {
  useState,
} from "react"



import {
  CheckCircle,
  XCircle,
  Loader2,
} from "lucide-react"



import {
  api,
} from "../../services/api"



import ApprovalExecutionFeedback from "./ApprovalExecutionFeedback"





export default function ApprovalActions(
  {
    approval,
    onApproved,
    onRejected,
    onCompleted,
  }
) {



  const [
    loading,
    setLoading,
  ] = useState(false)



  const [
    error,
    setError,
  ] = useState("")



  const [
    execution,
    setExecution,
  ] = useState(null)





  if (!approval) {

    return (

      <div className="panel">

        Select approval request

      </div>

    )

  }







  async function approve() {


    try {


      setLoading(true)

      setError("")



      const data =
        await api.approvalDashboardApprove(
          approval.approval_id
        )



      setExecution(
        data.execution ||
        null
      )



      if (onApproved) {

        onApproved(
          data
        )

      }



      if (onCompleted) {

        onCompleted()

      }



    }
    catch(error) {


      console.error(
        error
      )


      setError(
        error.message ||
        "Approve failed"
      )


    }
    finally {


      setLoading(false)


    }


  }







  async function reject() {


    try {


      setLoading(true)

      setError("")



      const data =
        await api.approvalDashboardReject(
          approval.approval_id,
          "Rejected by administrator"
        )



      setExecution(
        data.execution ||
        null
      )



      if (onRejected) {

        onRejected(
          data
        )

      }



      if (onCompleted) {

        onCompleted()

      }



    }
    catch(error) {


      console.error(
        error
      )


      setError(
        error.message ||
        "Reject failed"
      )


    }
    finally {


      setLoading(false)


    }


  }








  return (

    <section className="panel">


      <h3>

        Approval Actions

      </h3>





      {
        error &&


        <div className="panel error-banner">

          {error}

        </div>

      }







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








      <div className="approval-actions">



        <button

          disabled={loading}

          onClick={approve}

        >


          {

            loading ?

            <Loader2 size={18}/>

            :

            <CheckCircle size={18}/>

          }


          {" "}

          Approve


        </button>







        <button

          disabled={loading}

          onClick={reject}

        >


          {

            loading ?

            <Loader2 size={18}/>

            :

            <XCircle size={18}/>

          }


          {" "}

          Reject


        </button>



      </div>









      {
        execution &&


        <ApprovalExecutionFeedback

          execution={
            execution
          }

        />


      }






    </section>

  )

}
