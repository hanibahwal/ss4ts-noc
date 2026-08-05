import {
  Suspense,
  lazy,
} from "react";


import {
  BrowserRouter,
  Route,
  Routes,
} from "react-router-dom";


import AppLayout from "./components/layout/AppLayout";

import AppErrorBoundary from "./components/common/AppErrorBoundary";

import "./App.css";



// =====================================================
// Core Pages
// =====================================================


const Dashboard = lazy(
  () => import("./pages/Dashboard")
);


const Devices = lazy(
  () => import("./pages/Devices")
);


const DeviceDetails = lazy(
  () => import("./pages/DeviceDetails")
);


const LTE = lazy(
  () => import("./pages/LTE")
);


const Maps = lazy(
  () => import("./pages/Maps")
);


const Topology = lazy(
  () => import("./pages/Topology")
);


const Alerts = lazy(
  () => import("./pages/Alerts")
);


const Settings = lazy(
  () => import("./pages/Settings")
);




// =====================================================
// H23.4.5.5.12.X.4.5.5
// SS4TS AI Autonomous Executive NOC
// =====================================================


const ExecutiveDashboardV2 = lazy(
  () =>
    import(
      "./pages/ExecutiveDashboardV2"
    )
);




// =====================================================
// H23.4.5.5.12.X.4.6
// Human Approval Center
// =====================================================


const ApprovalCenter = lazy(
  () =>
    import(
      "./pages/ApprovalCenter"
    )
);




// =====================================================
// Loading Component
// =====================================================


function RouteFallback(){

  return (

    <div
      className="route-loading"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >

      جاري تحميل SS4TS AI NOC...

    </div>

  );

}




// =====================================================
// Application Router
// =====================================================


export default function App(){


  return (

    <AppErrorBoundary>


      <BrowserRouter>


        <Suspense
          fallback={
            <RouteFallback />
          }
        >


          <Routes>


            <Route
              element={
                <AppLayout />
              }
            >



              {/* =========================
                  Main Dashboard
              ========================== */}


              <Route
                path="/"
                element={
                  <Dashboard />
                }
              />



              {/* =========================
                  Devices
              ========================== */}


              <Route
                path="/devices"
                element={
                  <Devices />
                }
              />



              <Route
                path="/devices/:ip"
                element={
                  <DeviceDetails />
                }
              />



              {/* =========================
                  Network Views
              ========================== */}



              <Route
                path="/lte"
                element={
                  <LTE />
                }
              />



              <Route
                path="/maps"
                element={
                  <Maps />
                }
              />



              <Route
                path="/topology"
                element={
                  <Topology />
                }
              />



              {/* =========================
                  Alerts
              ========================== */}



              <Route
                path="/alerts"
                element={
                  <Alerts />
                }
              />




              {/* =========================
                  System Settings
              ========================== */}



              <Route
                path="/settings"
                element={
                  <Settings />
                }
              />





              {/* =================================================
                  H23.4.5.5.12.X.4.5.5

                  AI Executive Decision Support Center

                  Flow:

                  Collector
                      ↓
                  Prediction
                      ↓
                  Failure Forecast
                      ↓
                  Executive Decision
                      ↓
                  Response Planner
                      ↓
                  Human Approval

              ================================================= */}



              <Route
                path="/executive"
                element={
                  <ExecutiveDashboardV2 />
                }
              />





              {/* =================================================
                  H23.4.5.5.12.X.4.6

                  Human Approval & Authorization Center

              ================================================= */}



              <Route
                path="/approval-center"
                element={
                  <ApprovalCenter />
                }
              />



            </Route>



          </Routes>



        </Suspense>



      </BrowserRouter>



    </AppErrorBoundary>

  );

}
