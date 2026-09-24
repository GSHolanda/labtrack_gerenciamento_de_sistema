import { createContext, useContext } from 'react'

export type ToastTone = 'success' | 'danger' | 'info'

export interface ToastInput {
  tone?: ToastTone
  title: string
  message?: string
}

export const ToastContext = createContext<(toast: ToastInput) => void>(() => {})

/** Notificação curta após uma operação (ex.: "Resultado registrado"). */
export function useToast() {
  return useContext(ToastContext)
}
