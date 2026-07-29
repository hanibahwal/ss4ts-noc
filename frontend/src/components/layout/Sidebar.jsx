import {
  Bell,
  LayoutDashboard,
  Map,
  Network,
  RadioTower,
  Router,
  Settings,
  Share2,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const items = [
  { to: '/', label: 'لوحة التحكم', icon: LayoutDashboard },
  { to: '/devices', label: 'الأجهزة', icon: Router },
  { to: '/lte', label: 'LTE و5G', icon: RadioTower },
  { to: '/maps', label: 'الخرائط', icon: Map },
  { to: '/topology', label: 'Topology', icon: Share2 },
  { to: '/alerts', label: 'التنبيهات', icon: Bell },
  { to: '/settings', label: 'الإعدادات', icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">
          <Network size={28} />
        </div>

        <div>
          <strong>SS4TS NOC</strong>
          <span>Enterprise Platform</span>
        </div>
      </div>

      <nav className="navigation">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-status">
        <span className="status-dot online" />

        <div>
          <strong>خادم المراقبة</strong>
          <span>Operational</span>
        </div>
      </div>
    </aside>
  )
}
