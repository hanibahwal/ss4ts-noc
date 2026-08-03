import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'


import ApprovalDashboard from "../components/approval/ApprovalDashboard"



import {
  Activity,
  AlertTriangle,
  Cpu,
  MemoryStick,
  RadioTower,
  Router,
  Server,
  Wifi,
} from 'lucide-react'



import Header from '../components/layout/Header'


import RecentEvents from '../components/dashboard/RecentEvents'


import NotificationAuditIntelligenceCard from '../components/dashboard/NotificationAuditIntelligenceCard'


import NotificationAuditDecisionCard from '../components/dashboard/NotificationAuditDecisionCard'


import StatCard from '../components/dashboard/StatCard'


import TopCpuDevices from '../components/dashboard/TopCpuDevices'


import TrafficChart from '../components/dashboard/TrafficChart'


import { api } from '../services/api'


import { formatPercentage } from '../utils/formatters'





const EVENT_STORAGE_KEY =
  'ss4ts-noc-events'



const TRAFFIC_STORAGE_KEY =
  'ss4ts-noc-traffic'





function readStoredArray(key) {

  try {

    const value =
      JSON.parse(
        localStorage.getItem(key),
      )


    return Array.isArray(value)
      ? value
      : []


  } catch {

    return []

  }

}







export default function Dashboard() {


  const [
    devices,
    setDevices,
  ] = useState([])



  const [
    metrics,
    setMetrics,
  ] = useState({})



  // =====================================================
  // H23.4.5.5.12.20.5
  // Notification Audit Intelligence
  // =====================================================

  const [
    auditIntelligence,
    setAuditIntelligence,
  ] = useState(null)





  // =====================================================
  // H23.4.5.5.12.21.7.3
  // Notification Audit Decision
  // =====================================================

  const [
    auditDecision,
    setAuditDecision,
  ] = useState(null)





  const [
    trafficHistory,
    setTrafficHistory,
  ] = useState(() =>
    readStoredArray(
      TRAFFIC_STORAGE_KEY,
    ).slice(-30),
  )





  const [
    events,
    setEvents,
  ] = useState(() =>
    readStoredArray(
      EVENT_STORAGE_KEY,
    ).slice(0,50),
  )





  const [
    search,
    setSearch,
  ] = useState('')





  const [
    loading,
    setLoading,
  ] = useState(true)





  const [
    refreshing,
    setRefreshing,
  ] = useState(false)





  const [
    error,
    setError,
  ] = useState('')





  const [
    lastUpdated,
    setLastUpdated,
  ] = useState(null)





  const previousStatusRef =
    useRef({})





  function addEvents(newEvents) {


    if(newEvents.length === 0)
      return



    setEvents(
      current => {


        const next =
        [
          ...newEvents,
          ...current,
        ].slice(0,50)



        localStorage.setItem(
          EVENT_STORAGE_KEY,
          JSON.stringify(next),
        )



        return next

      },
    )


  }







  function detectEvents(
    deviceList,
    metricMap,
  ) {


    const detected = []


    const now =
      new Date()



    const readableTime =
      now.toLocaleTimeString(
        'ar-SA',
      )



    deviceList.forEach(
      device => {


        const previousStatus =
          previousStatusRef.current[
            device.ip
          ]



        const currentStatus =
          device.status



        const deviceMetrics =
          metricMap[
            device.ip
          ] || {}



        if(
          previousStatus &&
          previousStatus !== currentStatus
        ){


          detected.push({

            id:
              `${Date.now()}-${device.ip}`,

            type:
              currentStatus === 'online'
              ? 'recovered'
              : 'offline',


            title:
              currentStatus === 'online'
              ? 'تمت استعادة الجهاز'
              : 'الجهاز متوقف',


            message:
              `${device.name} — ${device.ip}`,


            time:
              readableTime,

          })


        }






        if(
          Number(deviceMetrics.cpu_usage)
          >= 90
        ){


          detected.push({

            id:
              `${Date.now()}-${device.ip}-cpu`,

            type:
              'cpu',


            title:
              'ارتفاع استخدام المعالج',


            message:
              `${device.name}: CPU ${deviceMetrics.cpu_usage}%`,


            time:
              readableTime,

          })


        }





        if(
          Number(deviceMetrics.temperature)
          >=70
        ){


          detected.push({

            id:
              `${Date.now()}-${device.ip}-temp`,


            type:
              'temperature',


            title:
              'ارتفاع درجة الحرارة',


            message:
              `${device.name}: ${deviceMetrics.temperature}°C`,


            time:
              readableTime,

          })


        }





        previousStatusRef.current[
          device.ip
        ] =
          currentStatus


      },
    )



    addEvents(
      detected,
    )

  function appendTraffic(metricMap){


    const values =
      Object.values(metricMap)



    const rxBps =
      values.reduce(
        (total,item)=>
          total +
          Number(
            item.rx_bps || 0,
          ),
        0,
      )



    const txBps =
      values.reduce(
        (total,item)=>
          total +
          Number(
            item.tx_bps || 0,
          ),
        0,
      )



    const point = {


      timestamp:
        Date.now(),



      time:
        new Date()
        .toLocaleTimeString(
          'ar-SA',
        ),



      rx_bps:
        rxBps,



      tx_bps:
        txBps,

    }





    setTrafficHistory(
      current => {


        const next =
        [
          ...current,
          point,
        ].slice(-30)



        localStorage.setItem(
          TRAFFIC_STORAGE_KEY,
          JSON.stringify(next),
        )



        return next


      },
    )


  }









  async function loadData(
    isRefresh=false,
  ){


    try {


      setError('')



      if(isRefresh)

        setRefreshing(true)

      else

        setLoading(true)





      const deviceList =
        await api.devices()






      const results =
        await Promise.allSettled(


          deviceList.map(
            async(device)=>{


              const data =
                await api.metrics(
                  device.ip,
                )



              return [
                device.ip,
                data,
              ]


            },
          ),

        )







      const metricMap = {}



      results.forEach(
        result=>{


          if(
            result.status ===
            'fulfilled'
          ){


            const [
              ip,
              data,
            ] =
              result.value



            metricMap[ip]=data


          }


        },
      )





      setDevices(
        deviceList,
      )


      setMetrics(
        metricMap,
      )






      // =====================================================
      // H23.4.5.5.12.20.5
      // Notification Audit Intelligence
      // =====================================================


      const intelligence =
        await api.notificationAuditIntelligence()



      setAuditIntelligence(
        intelligence,
      )






      // =====================================================
      // H23.4.5.5.12.21.7.3
      // Notification Audit Decision Engine
      // =====================================================


      const decision =
        await api.notificationAuditDecisionLatest()



      setAuditDecision(
        decision,
      )






      setLastUpdated(
        new Date(),
      )



      appendTraffic(
        metricMap,
      )



      detectEvents(
        deviceList,
        metricMap,
      )



    }


    catch(error){


      console.error(error)



      setError(

        error.message ||

        'تعذر تحميل بيانات لوحة التحكم',

      )


    }


    finally{


      setLoading(false)


      setRefreshing(false)


    }


  }








  useEffect(()=>{


    loadData()



    const interval =

      setInterval(

        ()=>loadData(true),

        30000,

      )



    return ()=>clearInterval(interval)


  },[])






  }


  const summary =
    useMemo(()=>{


      const online =

        devices.filter(

          d=>d.status==='online',

        ).length



      const offline =

        devices.length - online






      const values =

        Object.values(metrics)






      const averageCpu =

        values.length

        ?

        Math.round(

          values.reduce(

            (a,b)=>

              a +

              Number(

                b.cpu_usage || 0,

              ),

            0,

          )

          /

          values.length,

        )

        :

        0








      const averageMemory =


        values.length

        ?

        Math.round(

          values.reduce(

            (a,b)=>

              a +

              Number(

                b.memory_usage || 0,

              ),

            0,

          )

          /

          values.length,

        )

        :

        0








      return {


        total:

          devices.length,



        online,



        offline,



        averageCpu,



        averageMemory,



        health:


          devices.length

          ?

          Math.round(

            (

              online /

              devices.length

            )

            *

            100,

          )

          :

          0,


      }



    },[

      devices,

      metrics,

    ])












  const topCpuDevices =

    useMemo(()=>{


      return devices


      .map(

        device=>({


          ...device,


          cpu:


            Number(

              metrics[

                device.ip

              ]?.cpu_usage || 0,

            ),


        }),

      )


      .sort(

        (a,b)=>

          b.cpu - a.cpu,

      )



    },[

      devices,

      metrics,

    ])  
  


return (

<>

<Header

  title="لوحة التحكم"

  subtitle="ملخص شامل لحالة الشبكة والأجهزة والخدمات"

  onRefresh={
    ()=>loadData(true)
  }

  refreshing={
    refreshing
  }

  searchValue={
    search
  }

  onSearchChange={
    setSearch
  }

  lastUpdated={
    lastUpdated
  }

/>





{
  error &&

  <div className="error-banner">

    {error}

  </div>
}







<section className="stats-grid">


<StatCard

 title="إجمالي الأجهزة"

 value={
   summary.total
 }

 icon={
   Router
 }

/>



<StatCard

 title="الأجهزة المتصلة"

 value={
   summary.online
 }

 icon={
   Wifi
 }

 tone="green"

/>



<StatCard

 title="الأجهزة المتوقفة"

 value={
   summary.offline
 }

 icon={
   AlertTriangle
 }

 tone="red"

/>



<StatCard

 title="صحة الشبكة"

 value={
   `${summary.health}%`
 }

 icon={
   Activity
 }

/>



<StatCard

 title="متوسط CPU"

 value={
   formatPercentage(
     summary.averageCpu
   )
 }

 icon={
   Cpu
 }

/>



<StatCard

 title="متوسط الذاكرة"

 value={
   formatPercentage(
     summary.averageMemory
   )
 }

 icon={
   MemoryStick
 }

/>



<StatCard

 title="LTE و 5G"

 value={
   devices.length
 }

 icon={
   RadioTower
 }

/>



<StatCard

 title="الخدمات"

 value="4/4"

 icon={
   Server
 }

/>


</section>







<section className="dashboard-grid">





<TrafficChart

 data={
   trafficHistory
 }

/>





<TopCpuDevices

 devices={
   topCpuDevices
 }

/>





<RecentEvents

 events={
   events
 }

/>







{/* =====================================================
    H23.4.5.5.12.20.5
    Notification Audit Intelligence
===================================================== */}


<NotificationAuditIntelligenceCard

 data={
   auditIntelligence
 }

/>







{/* =====================================================
    H23.4.5.5.12.21.7.3
    Notification Audit Decision Engine
===================================================== */}


<NotificationAuditDecisionCard

 data={
   auditDecision
 }

/>



</section>







{/* =====================================================
    H23.4.5.5.12.22.10
    Approval Dashboard UI
===================================================== */}



<section className="dashboard-grid">

  <ApprovalDashboard />

</section>








{
 loading &&

 <div className="loading-overlay">


  <Activity

   className="spin"

   size={
    34
   }

  />



  <span>

    جاري تحميل بيانات الشبكة...

  </span>



 </div>

}




</>

)

}  



  
