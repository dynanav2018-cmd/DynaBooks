import { useLocation } from 'react-router-dom'

const titles = {
  '/dashboard': 'Dashboard',
  '/invoices': 'Invoices',
  '/contacts': 'Contacts',
  '/accounts': 'Chart of Accounts',
  '/reports': 'Reports',
  '/settings': 'Settings',
  '/journals': 'Journal Entries',
}

export default function TopBar() {
  const location = useLocation()
  const basePath = '/' + location.pathname.split('/')[1]
  const title = titles[basePath] || 'DynaBooks'

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center px-6 shrink-0">
      <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
    </header>
  )
}
