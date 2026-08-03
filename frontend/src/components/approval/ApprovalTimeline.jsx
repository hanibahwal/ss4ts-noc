export default function ApprovalTimeline({
  timeline,
}) {


  return (

    <div className="panel">

      <h3>
        Approval Timeline
      </h3>


      {
        !timeline ||
        timeline.length === 0

        ?

        <p>
          No timeline events
        </p>

        :

        timeline.map(
          (event, index) => (

            <div

              key={index}

              className="panel"

            >

              <h4>

                {event.type}

              </h4>


              <p>

                Status:
                {" "}
                {event.status}

              </p>


              {
                event.execution_id &&

                <p>

                  Execution:
                  {" "}
                  {event.execution_id}

                </p>

              }


              <small>

                {
                  event.timestamp
                }

              </small>


            </div>

          )

        )

      }


    </div>

  )

}
