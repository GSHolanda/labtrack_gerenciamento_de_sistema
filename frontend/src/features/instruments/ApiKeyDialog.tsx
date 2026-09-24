import { Check, Copy, KeyRound } from 'lucide-react'
import { useState } from 'react'

import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import type { InstrumentWithKey } from '../../types/api'

/** A chave existe em texto apenas nesta resposta: o banco guarda só o hash. */
export function ApiKeyDialog({
  instrument,
  rotated,
  onClose,
}: {
  instrument: InstrumentWithKey
  rotated: boolean
  onClose: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(instrument.api_key)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Modal title={`Chave de integração: ${instrument.code}`} onClose={onClose}>
      <div className="form">
        <Alert tone="warning" title="Copie a chave agora">
          Ela não será exibida novamente. Se for perdida, gere uma nova chave.
          {rotated && ' A chave anterior já deixou de funcionar.'}
        </Alert>
        <div className="api-key">
          <KeyRound aria-hidden />
          <code data-testid="api-key">{instrument.api_key}</code>
        </div>
        <p className="muted">
          O equipamento envia a chave no header <code>X-Instrument-Key</code>. No simulador, use{' '}
          <code>--key {instrument.code}=&lt;chave&gt;</code> ou o arquivo <code>config.json</code>.
        </p>
        <div className="form__actions">
          <Button icon={copied ? <Check aria-hidden /> : <Copy aria-hidden />} onClick={copy}>
            {copied ? 'Copiada' : 'Copiar chave'}
          </Button>
          <Button variant="primary" onClick={onClose}>
            Concluir
          </Button>
        </div>
      </div>
    </Modal>
  )
}
