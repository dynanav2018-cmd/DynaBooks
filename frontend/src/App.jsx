import { Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './hooks/useToast'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import InvoiceList from './pages/invoices/InvoiceList'
import InvoiceForm from './pages/invoices/InvoiceForm'
import InvoiceDetail from './pages/invoices/InvoiceDetail'
import ContactList from './pages/contacts/ContactList'
import AccountList from './pages/accounts/AccountList'
import ReportsIndex from './pages/reports/ReportsIndex'
import SettingsIndex from './pages/settings/SettingsIndex'

function ComingSoon({ title }) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-gray-700 mb-2">{title}</h2>
        <p className="text-gray-500">Coming in Phase 4</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="invoices" element={<InvoiceList />} />
          <Route path="invoices/new" element={<InvoiceForm />} />
          <Route path="invoices/:id" element={<InvoiceDetail />} />
          <Route path="invoices/:id/edit" element={<InvoiceForm />} />
          <Route path="contacts" element={<ContactList />} />
          <Route path="accounts" element={<AccountList />} />
          <Route path="reports" element={<ReportsIndex />} />
          <Route path="reports/:type" element={<ReportsIndex />} />
          <Route path="settings" element={<SettingsIndex />} />
          <Route path="journals" element={<ComingSoon title="Journal Entries" />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}
