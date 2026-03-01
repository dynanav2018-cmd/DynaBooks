import { useLocation, Link } from 'react-router-dom'
import { useCompany } from '../../hooks/useCompany'

const titles = {
  '/dashboard': 'Dashboard',
  '/invoices': 'Invoices',
  '/bills': 'Bills',
  '/contacts': 'Contacts',
  '/accounts': 'Chart of Accounts',
  '/reports': 'Reports',
  '/settings': 'Settings',
  '/journals': 'Journal Entries',
  '/banking': 'Banking',
  '/closing': 'Year-End Close',
  '/companies': 'Companies',
}

export default function TopBar() {
  const location = useLocation()
  const basePath = '/' + location.pathname.split('/')[1]
  const title = titles[basePath] || 'DynaBooks'
  const { company } = useCompany()

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
      <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
      {company && (
        <Link to="/companies" className="text-sm text-gray-500 hover:text-accent">
          {company.name}
        </Link>
      )}
    </header>
  )
}
