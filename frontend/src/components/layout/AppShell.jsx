import { Outlet, Navigate } from 'react-router-dom'
import { useCompany } from '../../hooks/useCompany'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function AppShell() {
  const { company } = useCompany()

  if (!company) {
    return <Navigate to="/companies" replace />
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6 bg-gray-50">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
