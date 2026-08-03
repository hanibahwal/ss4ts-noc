import {
  useEffect,
  useState,
} from "react"


import {
  Activity,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"



import {
  api,
} from "../../services/api"



import ApprovalSummaryCards from "./ApprovalSummaryCards"

import ApprovalQueue from "./ApprovalQueue"

import ApprovalTimeline from "./ApprovalTimeline"

import ApprovalActions from "./ApprovalActions"



export default function ApprovalDashboard() {


  const [
    summary,
    setSummary,
  ] = useState(null)



  const [
    approvals,
    setApprovals,
  ] = useState([])



  const [
    selectedApproval,
    setSelectedApproval,
  ] = useState(null)



  const [
    timeline,
    setTimeline,
  ] = useState([])



  const [
    loading,
    setLoading,
  ] = useState(false)



  const [
    error,
    setError,
  ] = useState("")




  async function loadDashboard() {


    try {


      setLoading(true)

      setError("")



      const [
        summaryData,
        pendingData,
      ] = await Promise.all([


        api.approvalDashboardSummary(),


        api.approvalDashboardPending(),


      ])




      setSummary(
        summaryData
      )



      setApprovals(
        pendingData
      )



    }

    catch(err) {


      console.error(err)


      setError(
        err.message ||
        "Failed loading approval dashboard"
      )


    }


    finally {


      setLoading(false)


    }


  }





  async function loadTimeline(
    approvalId
  ) {


    try {


      const data =
        await api.approvalDashboardTimeline(
          approvalId
        )



      setTimeline(
        data.events || []
      )



    }

    catch(err) {


      console.error(err)


      setTimeline([])


    }


  }






  function selectApproval(
    approval
  ) {


    setSelectedApproval(
      approval
    )


    loadTimeline(
      approval.approval_id
    )


  }






  useEffect(
    () => {


      loadDashboard()



      const timer =
        setInterval(
          loadDashboard,
          60000
        )



      return () =>
        clearInterval(timer)



    },
    []
  )







  return (

    <section className="panel wide-panel">


      <div className="panel-header">


        <div>


          <p className="eyebrow">

            Autonomous Response

          </p>



          <h3>

            Approval Dashboard

          </h3>


        </div>




        <button
          className="icon-button"
          onClick={loadDashboard}
          disabled={loading}
        >

          <RefreshCw size={18}/>

        </button>



      </div>






      {
        error &&

        <div className="panel error-banner">

          {error}

        </div>

      }







      <ApprovalSummaryCards

        summary={
          summary
        }

      />







      <div className="approval-layout">



        <div>


          <ApprovalQueue

            approvals={
              approvals
            }


            selected={
              selectedApproval
            }


            onSelect={
              selectApproval
            }


          />


        </div>







        <div>


          {

            selectedApproval &&

            <ApprovalTimeline

              approval={
                selectedApproval
              }


              events={
                timeline
              }


            />

          }



          {

            !selectedApproval &&

            <div className="panel">


              <Activity size={24}/>


              <p>

                Select approval to view lifecycle

              </p>


            </div>


          }



        </div>



      </div>







      <div className="panel">


        <ShieldCheck size={20}/>


        <p>

          AI Decision → Approval → Execution Runtime

        </p>


      </div>





    </section>

  )

}
