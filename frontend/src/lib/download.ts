// Entrega ao navegador um arquivo recebido da API (ex.: PDF do relatório).

export function saveFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.append(link)
  link.click()
  link.remove()
  // O download já começou; liberar a URL em seguida não o interrompe.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
