export default function ApprovalQueue({
  approvals,
  selected,
  onSelect,
}) {


  return (

    <div className="panel">

      <h3>
        Approval Queue
      </h3>


      {
        approvals.length === 0 &&

        <p>
          No pending approvals
        </p>

      }



      {
        approvals.map(

          (approval) => (

            <div

              key={
                approval.approval_id
              }


              className="panel"

              onClick={
                () =>
                  onSelect(
                    approval
                  )
              }


              style={{

                cursor:
                  "pointer",

                border:
                  selected?.approval_id === approval.approval_id
                  ?
                  "2px solid #2563eb"
                  :
                  undefined,

              }}

            >


              <h4>

                {approval.action_type}

              </h4>


              <p>

                Status:
                {" "}
                {approval.status}

              </p>


              <p>

                Reason:
                {" "}

                {
                  approval.requested_reason
                }

              </p>


            </div>

          )

        )

      }


    </div>

  )

}
