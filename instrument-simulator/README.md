# LabTrack — Instrument Simulator

Módulo **separado** do backend que simula equipamentos de laboratório
(pHmetro, HPLC, balança, densímetro...) enviando resultados ao LabTrack via
API REST, como um driver de instrumento ou middleware de integração faria.

> Status: estrutura criada na ETAPA 1. A implementação acontece na **ETAPA 8**.

## Como vai funcionar

```
┌──────────────────────┐   GET  /api/v1/instruments/worklist   ┌──────────────┐
│ Instrument Simulator │ ────────────────────────────────────▶ │ LabTrack API │
│  (PH-METER-01 ...)   │   POST /api/v1/instruments/results    │              │
│                      │ ────────────────────────────────────▶ │  valida,     │
│                      │   POST /api/v1/instruments/heartbeat  │  registra e  │
│                      │ ────────────────────────────────────▶ │  audita      │
└──────────────────────┘   Header: X-Instrument-Key            └──────────────┘
```

1. Cada instrumento se autentica com a **própria chave de API** (`X-Instrument-Key`).
2. Consulta a **worklist**: testes pendentes, compatíveis com o seu tipo, em
   amostras que estão em análise.
3. Gera um valor em torno da especificação (com uma probabilidade configurável
   de resultado **OOS**) e envia:

```json
{
  "instrument_id": "PH-METER-01",
  "sample_code": "SMP-2026-0001",
  "test": "PH",
  "result": 7.21,
  "unit": "pH"
}
```

4. Envia *heartbeats* periódicos, que alimentam o status "online" e a "última
   comunicação" na tela de equipamentos.
