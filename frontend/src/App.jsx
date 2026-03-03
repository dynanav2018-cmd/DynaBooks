import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './hooks/useToast'
import { CompanyProvider } from './hooks/useCompany'
import { SettingsProvider } from './hooks/useSettings'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import InvoiceList from './pages/invoices/InvoiceList'
import InvoiceForm from './pages/invoices/InvoiceForm'
import InvoiceDetail from './pages/invoices/InvoiceDetail'
import BillList from './pages/bills/BillList'
import BillForm from './pages/bills/BillForm'
import BillDetail from './pages/bills/BillDetail'
import JournalList from './pages/journals/JournalList'
import JournalForm from './pages/journals/JournalForm'
import BankingIndex from './pages/banking/BankingIndex'
import ContactList from './pages/contacts/ContactList'
import AccountList from './pages/accounts/AccountList'
import AccountDetail from './pages/accounts/AccountDetail'
import ReportsIndex from './pages/reports/ReportsIndex'
import SettingsIndex from './pages/settings/SettingsIndex'
import ClosingIndex from './pages/closing/ClosingIndex'
import CompanySelector from './pages/company/CompanySelector'

export default function App() {
  useEffect(() => {
    fetch('/api/build-config')
      .then(r => r.json())
      .then(cfg => { document.title = cfg.app_name || 'DynaBooks' })
      .catch(() => {})
  }, [])

  return (
    <CompanyProvider>
      <SettingsProvider>
      <ToastProvider>
        <Routes>
          <Route path="companies" element={<CompanySelector />} />
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="invoices" element={<InvoiceList />} />
            <Route path="invoices/new" element={<InvoiceForm />} />
            <Route path="invoices/:id" element={<InvoiceDetail />} />
            <Route path="invoices/:id/edit" element={<InvoiceForm />} />
            <Route path="bills" element={<BillList />} />
            <Route path="bills/new" element={<BillForm />} />
            <Route path="bills/:id" element={<BillDetail />} />
            <Route path="bills/:id/edit" element={<BillForm />} />
            <Route path="journals" element={<JournalList />} />
            <Route path="journals/new" element={<JournalForm />} />
            <Route path="journals/:id/edit" element={<JournalForm />} />
            <Route path="banking" element={<BankingIndex />} />
            <Route path="contacts" element={<ContactList />} />
            <Route path="accounts" element={<AccountList />} />
            <Route path="accounts/:id" element={<AccountDetail />} />
            <Route path="reports" element={<ReportsIndex />} />
            <Route path="reports/:type" element={<ReportsIndex />} />
            <Route path="settings" element={<SettingsIndex />} />
            <Route path="closing" element={<ClosingIndex />} />
          </Route>
        </Routes>
      </ToastProvider>
      </SettingsProvider>
    </CompanyProvider>
  )
}
