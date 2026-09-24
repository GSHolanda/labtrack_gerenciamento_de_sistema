import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { type ReactNode, useCallback, useState } from 'react'

import { type ToastInput, ToastContext } from './toastContext'

interface Toast extends ToastInput {
  id: number
}

const ICONS = { success: CircleCheck, danger: CircleAlert, info: Info }
let nextId = 1

export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback(
    (toast: ToastInput) => {
      const id = nextId++
      setToasts((current) => [...current.slice(-3), { ...toast, id }])
      window.setTimeout(() => dismiss(id), toast.tone === 'danger' ? 8000 : 4500)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toaster" aria-live="polite">
        {toasts.map(({ id, tone = 'success', title, message }) => {
          const Icon = ICONS[tone]
          return (
            <div key={id} className={`toast toast--${tone}`} role="status">
              <Icon aria-hidden />
              <div>
                <strong>{title}</strong>
                {message && <p>{message}</p>}
              </div>
              <button type="button" onClick={() => dismiss(id)} aria-label="Fechar notificação">
                <X aria-hidden />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
