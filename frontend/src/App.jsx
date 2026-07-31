import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import './App.css'

const Alerts = lazy(() => import('./pages/Alerts'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const DeviceDetails = lazy(() => import('./pages/DeviceDetails'))
const Devices = lazy(() => import('./pages/Devices'))
const LTE = lazy(() => import('./pages/LTE'))
const Maps = lazy(() => import('./pages/Maps'))
const Settings = lazy(() => import('./pages/Settings'))
const Topology = lazy(() => import('./pages/Topology'))


function RouteFallback() {
  return (
    <div
      className="route-loading"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      جارٍ تحميل الصفحة...
    </div>
  )
}


export default function App() {
  return (
    <BrowserRouter>
      <Suspense
        fallback={<RouteFallback />}
      >
        <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices" element={<Devices />} />
          <Route
            path="/devices/:ip"
            element={<DeviceDetails />}
          />
          <Route path="/lte" element={<LTE />} />
          <Route path="/maps" element={<Maps />} />
          <Route path="/topology" element={<Topology />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
