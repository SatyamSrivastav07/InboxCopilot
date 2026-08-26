import axios from 'axios'

// Development talks to the local FastAPI server. Production defaults to same-origin
// `/api` requests: Docker uses Nginx and Vercel uses the checked-in proxy function.
// This keeps the signed browser session first-party instead of depending on a
// cross-site Render cookie.
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60_000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function apiError(error, fallback) {
  const structuredMessage = error.response?.data?.error?.message
  if (typeof structuredMessage === 'string') {
    return new Error(structuredMessage)
  }
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') {
    return new Error(detail)
  }
  if (error.code === 'ECONNABORTED') {
    return new Error('The request timed out. Please try again.')
  }
  return new Error(fallback)
}

export async function analyzeEmail(email) {
  try {
    const { data } = await api.post('/api/analyze-email', email)
    return data
  } catch (error) {
    throw apiError(error, 'Could not reach the analysis service. Check that the backend is running.')
  }
}

export async function getGmailStatus() {
  try {
    const { data } = await api.get('/api/gmail/status')
    return data
  } catch (error) {
    throw apiError(error, 'Could not check the Gmail connection.')
  }
}

export async function getAuthSession() {
  try {
    const { data } = await api.get('/api/auth/session')
    return data
  } catch (error) {
    throw apiError(error, 'Could not check your sign-in session.')
  }
}

export async function getGoogleAuthUrl() {
  try {
    const { data } = await api.get('/api/auth/google')
    return data.authorization_url
  } catch (error) {
    throw apiError(error, 'Could not start Google sign-in.')
  }
}

export async function logout() {
  try {
    const { data } = await api.post('/api/auth/logout')
    return data
  } catch (error) {
    throw apiError(error, 'Could not sign out.')
  }
}

export async function getGmailAuthUrl() {
  return getGoogleAuthUrl()
}

export async function syncGmailInbox(options) {
  try {
    const { data } = await api.post('/api/gmail/sync', options)
    return data
  } catch (error) {
    throw apiError(error, 'Could not sync the Gmail inbox.')
  }
}

export async function getJobStatus(jobId) {
  try {
    const { data } = await api.get(`/api/jobs/${jobId}`)
    return data
  } catch (error) {
    throw apiError(error, 'Could not load background job progress.')
  }
}

export async function reprocessEmail(emailId) {
  try {
    const { data } = await api.post(`/api/emails/${emailId}/reprocess`)
    return data
  } catch (error) {
    throw apiError(error, 'Could not queue email reprocessing.')
  }
}

export async function queueInboxReindex() {
  try {
    const { data } = await api.post('/api/search/reindex')
    return data
  } catch (error) {
    throw apiError(error, 'Could not queue inbox reindexing.')
  }
}

export async function getDashboardStats() {
  try {
    const { data } = await api.get('/api/dashboard')
    return data
  } catch (error) {
    throw apiError(error, 'Could not load dashboard data.')
  }
}

export async function getPersistedEmails(filters = {}) {
  try {
    const { data } = await api.get('/api/emails', { params: filters })
    return data
  } catch (error) {
    throw apiError(error, 'Could not load persisted emails.')
  }
}

export async function getPersistedEmail(emailId) {
  try {
    const { data } = await api.get(`/api/emails/${emailId}`)
    return data
  } catch (error) {
    throw apiError(error, 'Could not load the email details.')
  }
}

export async function getTasks(filters = {}) {
  try {
    const { data } = await api.get('/api/tasks', { params: filters })
    return data
  } catch (error) {
    throw apiError(error, 'Could not load tasks.')
  }
}

export async function updateTask(taskId, completed) {
  try {
    const { data } = await api.patch(`/api/tasks/${taskId}`, { completed })
    return data
  } catch (error) {
    throw apiError(error, 'Could not update the task.')
  }
}

export async function getMeetings(filters = {}) {
  try {
    const { data } = await api.get('/api/meetings', { params: filters })
    return data
  } catch (error) {
    throw apiError(error, 'Could not load meetings.')
  }
}

export async function semanticSearch(query, options = {}) {
  try {
    const { data } = await api.post('/api/search/semantic', {
      query,
      top_k: options.topK || 5,
      filters: options.filters || undefined,
    })
    return data
  } catch (error) {
    throw apiError(error, 'Could not search the indexed inbox.')
  }
}

export async function askInbox(question) {
  try {
    const { data } = await api.post('/api/chat/inbox', {
      question,
    })
    return data
  } catch (error) {
    throw apiError(error, 'Could not answer from the inbox right now.')
  }
}

export async function generateReplyDraft(emailId, options) {
  try {
    const { data } = await api.post(`/api/emails/${emailId}/draft-reply`, options, { timeout: 2 * 60_000 })
    return data
  } catch (error) {
    throw apiError(error, 'Could not generate the reply draft.')
  }
}

export async function updateReplyDraft(draftId, body) {
  try {
    const { data } = await api.patch(`/api/drafts/${draftId}`, { body })
    return data
  } catch (error) {
    throw apiError(error, 'Could not save the edited draft.')
  }
}

export async function approveReplyDraft(draftId) {
  try {
    const { data } = await api.post(`/api/drafts/${draftId}/approve`)
    return data
  } catch (error) {
    throw apiError(error, 'Could not approve the draft.')
  }
}

export async function sendReplyDraft(draftId) {
  try {
    const { data } = await api.post(`/api/drafts/${draftId}/send`)
    return data
  } catch (error) {
    throw apiError(error, 'Could not send the approved reply.')
  }
}
