import { useEffect, useState } from 'react'

export default function PWAInstallButton() {
  const [installPrompt, setInstallPrompt] = useState(null)

  useEffect(() => {
    const capturePrompt = (event) => {
      event.preventDefault()
      setInstallPrompt(event)
    }
    const clearPrompt = () => setInstallPrompt(null)

    window.addEventListener('beforeinstallprompt', capturePrompt)
    window.addEventListener('appinstalled', clearPrompt)
    return () => {
      window.removeEventListener('beforeinstallprompt', capturePrompt)
      window.removeEventListener('appinstalled', clearPrompt)
    }
  }, [])

  if (!installPrompt) return null

  const install = async () => {
    await installPrompt.prompt()
    await installPrompt.userChoice
    setInstallPrompt(null)
  }

  return (
    <button
      className="install-app-button rounded-lg border px-3 py-2 text-sm font-semibold transition hover:-translate-y-px"
      type="button"
      onClick={() => install().catch(() => setInstallPrompt(null))}
    >
      Install app
    </button>
  )
}
