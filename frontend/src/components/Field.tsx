import {
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from 'react'

interface FieldProps {
  label: string
  error?: string
  hint?: ReactNode
  required?: boolean
  children: (id: string, describedBy: string | undefined) => ReactNode
}

export function Field({ label, error, hint, required, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={error ? 'field field--invalid' : 'field'}>
      <label htmlFor={id}>
        {label}
        {required && <span className="field__required"> *</span>}
      </label>
      {children(id, describedBy)}
      {error ? (
        <span id={`${id}-error`} className="field__error">
          {error}
        </span>
      ) : (
        hint && (
          <span id={`${id}-hint`} className="field__hint">
            {hint}
          </span>
        )
      )}
    </div>
  )
}

type Common = { label: string; error?: string; hint?: ReactNode }

export function TextField({
  label,
  error,
  hint,
  required,
  ...props
}: Common & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <input
          id={id}
          className="input"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          required={required}
          {...props}
        />
      )}
    </Field>
  )
}

export function SelectField({
  label,
  error,
  hint,
  required,
  children,
  ...props
}: Common & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <select
          id={id}
          className="input"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          required={required}
          {...props}
        >
          {children}
        </select>
      )}
    </Field>
  )
}

export function TextAreaField({
  label,
  error,
  hint,
  required,
  ...props
}: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <textarea
          id={id}
          className="input"
          rows={3}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          required={required}
          {...props}
        />
      )}
    </Field>
  )
}

export function CheckboxField({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  hint?: string
}) {
  return (
    <label className="checkbox">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        {label}
        {hint && <small>{hint}</small>}
      </span>
    </label>
  )
}
