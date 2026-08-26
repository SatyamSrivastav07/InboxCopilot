import { Navigate, Route, Routes } from 'react-router-dom'

import AppHeader from './components/AppHeader.jsx'
import AppFooter from './components/AppFooter.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import GmailInboxPage from './pages/GmailInboxPage.jsx'
import InboxPage from './pages/InboxPage.jsx'
import MeetingsPage from './pages/MeetingsPage.jsx'
import HomePage from './pages/HomePage.jsx'
import TasksPage from './pages/TasksPage.jsx'
import AssistantPage from './pages/AssistantPage.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import PublicHomePage from './pages/PublicHomePage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import DataDeletionPage from './pages/DataDeletionPage.jsx'
import { AuthProvider, useAuth } from './auth/AuthContext.jsx'

function ProtectedRoutes() {
  const { loading, session } = useAuth()
  if (loading) return <div className="grid min-h-[70vh] place-items-center text-sm text-slate-500">Checking your secure session…</div>
  if (!session?.authenticated) {
    return <Routes>
      <Route path="/" element={<PublicHomePage />} />
      <Route path="/gmail" element={<GmailInboxPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  }
  return <Routes>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/inbox" element={<InboxPage />} />
    <Route path="/tasks" element={<TasksPage />} />
    <Route path="/meetings" element={<MeetingsPage />} />
    <Route path="/analyze" element={<HomePage />} />
    <Route path="/gmail" element={<GmailInboxPage />} />
    <Route path="/assistant" element={<AssistantPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}

export default function App() {
  return (
    <AuthProvider>
      <main className="flex min-h-screen flex-col">
        <AppHeader />
        <div className="flex-1">
          <Routes>
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/data-deletion" element={<DataDeletionPage />} />
            <Route path="*" element={<ProtectedRoutes />} />
          </Routes>
        </div>
        <AppFooter />
      </main>
    </AuthProvider>
  )
}
