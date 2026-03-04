import { NavLink, useLocation, Link } from 'react-router-dom'
import { useState } from 'react'
import { useCompany } from '../../hooks/useCompany'

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4' },
  {
    label: 'Sales',
    icon: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2v16z',
    children: [
      { label: 'Invoices', path: '/invoices' },
      { label: 'Clients', path: '/contacts?type=client' },
    ],
  },
  {
    label: 'Purchases',
    icon: 'M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z',
    children: [
      { label: 'Bills', path: '/bills' },
      { label: 'Suppliers', path: '/contacts?type=supplier' },
    ],
  },
  {
    label: 'Accounting',
    icon: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z',
    children: [
      { label: 'Journal Entries', path: '/journals' },
      { label: 'Chart of Accounts', path: '/accounts' },
      { label: 'Year-End Close', path: '/closing' },
    ],
  },
  {
    label: 'Banking',
    icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
    children: [
      { label: 'Receipts & Payments', path: '/banking' },
      { label: 'Bank Reconciliation', path: '/banking/reconciliation' },
    ],
  },
  { label: 'Reports', path: '/reports', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: 'Settings', path: '/settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]

function NavIcon({ d }) {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={d} />
    </svg>
  )
}

export default function Sidebar() {
  const location = useLocation()
  const [expanded, setExpanded] = useState({})
  const { company } = useCompany()

  const toggleExpand = (label) => {
    setExpanded((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  const isActive = (path) => {
    const basePath = path.split('?')[0]
    return location.pathname === basePath || location.pathname.startsWith(basePath + '/')
  }

  return (
    <aside className="w-60 bg-navy text-white flex flex-col min-h-screen">
      <div className="px-5 py-5 border-b border-navy-light">
        <h1 className="text-xl font-bold tracking-tight">DynaBooks</h1>
        <p className="text-xs text-blue-300 mt-0.5">
          {company?.name || 'DynaNav Systems Inc.'}
        </p>
        {company && (
          <Link to="/companies" className="text-xs text-blue-400 hover:text-white mt-1 inline-block">
            Switch Company
          </Link>
        )}
      </div>
      <nav className="flex-1 py-3 overflow-y-auto">
        {navItems.map((item) =>
          item.children ? (
            <div key={item.label}>
              <button
                onClick={() => toggleExpand(item.label)}
                className="w-full flex items-center gap-3 px-5 py-2.5 text-sm text-blue-200 hover:bg-navy-light transition-colors"
              >
                <NavIcon d={item.icon} />
                <span className="flex-1 text-left">{item.label}</span>
                <svg
                  className={`w-4 h-4 transition-transform ${expanded[item.label] ? 'rotate-90' : ''}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
              {expanded[item.label] && (
                <div className="ml-8 border-l border-navy-light">
                  {item.children.map((child) => (
                    <NavLink
                      key={child.path}
                      to={child.path}
                      className={`block px-4 py-2 text-sm transition-colors ${
                        isActive(child.path)
                          ? 'text-white bg-navy-light'
                          : 'text-blue-300 hover:text-white hover:bg-navy-light'
                      }`}
                    >
                      {child.label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                isActive(item.path)
                  ? 'text-white bg-navy-light border-r-3 border-accent'
                  : 'text-blue-200 hover:text-white hover:bg-navy-light'
              }`}
            >
              <NavIcon d={item.icon} />
              {item.label}
            </NavLink>
          ),
        )}
      </nav>
    </aside>
  )
}
