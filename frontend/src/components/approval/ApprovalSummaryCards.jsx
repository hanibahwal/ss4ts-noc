import {
  Clock,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react"



export default function ApprovalSummaryCards({
  summary
}) {


  const cards = [

    {
      title:
        "Pending",

      value:
        summary?.total_pending ?? 0,

      icon:
        Clock,

    },


    {
      title:
        "High Risk",

      value:
        summary?.high_risk ?? 0,

      icon:
        ShieldAlert,

    },


    {
      title:
        "Medium Risk",

      value:
        summary?.medium_risk ?? 0,

      icon:
        AlertTriangle,

    },


    {
      title:
        "Approved Today",

      value:
        summary?.approved_today ?? 0,

      icon:
        ShieldCheck,

    },

  ]



  return (

    <div className="stats-grid">


      {
        cards.map(
          (
            card
          ) => {


            const Icon =
              card.icon



            return (

              <div
                className="panel"
                key={
                  card.title
                }
              >

                <Icon
                  size={24}
                />


                <p>
                  {card.title}
                </p>


                <h2>
                  {card.value}
                </h2>


              </div>

            )


          }

        )

      }


    </div>

  )

}
