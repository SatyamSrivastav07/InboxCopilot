import { useState } from 'react'

import AnalysisResult from '../components/AnalysisResult.jsx'
import EmailForm from '../components/EmailForm.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { analyzeEmail } from '../services/api.js'

export default function HomePage() {
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleAnalyze = async (email) => {
    setIsLoading(true)
    setError('')
    try {
      setAnalysis(await analyzeEmail(email))
    } catch (requestError) {
      setAnalysis(null)
      setError(requestError.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl items-start gap-6 px-5 py-8 sm:px-8 lg:grid-cols-[0.9fr_1.1fr]">
        <EmailForm isLoading={isLoading} onAnalyze={handleAnalyze} />
        <div>
          {error && (
            <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
              <span className="font-semibold">Analysis failed. </span>{error}
            </div>
          )}
          {analysis ? <AnalysisResult analysis={analysis} /> : <EmptyState />}
        </div>
    </div>
  )
}
