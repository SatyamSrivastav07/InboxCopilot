import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

function apiError(error, fallback) {
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

export async function getGmailAuthUrl() {
  try {
    const { data } = await api.get('/api/gmail/auth-url')
    return data.authorization_url
  } catch (error) {
    throw apiError(error, 'Could not start Gmail authorization.')
  }
}

export async function syncGmailInbox(options) {
  try {
    const { data } = await api.post('/api/gmail/sync', options, { timeout: 10 * 60_000 })
    return data
  } catch (error) {
    throw apiError(error, 'Could not sync the Gmail inbox.')
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

export async function askInbox(question, options = {}) {
  try {
    const { data } = await api.post('/api/chat/inbox', {
      question,
      top_k: options.topK || undefined,
      filters: options.filters || undefined,
    })
    return data
  } catch (error) {
    throw apiError(error, 'Could not answer from the inbox right now.')
  }
}
