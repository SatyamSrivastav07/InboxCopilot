import { Navigate, Route, Routes } from 'react-router-dom'

import AppHeader from './components/AppHeader.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import GmailInboxPage from './pages/GmailInboxPage.jsx'
import InboxPage from './pages/InboxPage.jsx'
import MeetingsPage from './pages/MeetingsPage.jsx'
import HomePage from './pages/HomePage.jsx'
import TasksPage from './pages/TasksPage.jsx'
import AssistantPage from './pages/AssistantPage.jsx'

export default function App() {
  return (
    <main className="min-h-screen">
      <AppHeader />
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/analyze" element={<HomePage />} />
        <Route path="/gmail" element={<GmailInboxPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  )
}
