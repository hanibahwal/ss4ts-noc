import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import Alerts from './pages/Alerts'
import Dashboard from './pages/Dashboard'
import DeviceDetails from './pages/DeviceDetails'
import Devices from './pages/Devices'
import LTE from './pages/LTE'
import Maps from './pages/Maps'
import Settings from './pages/Settings'
import Topology from './pages/Topology'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  )
}
