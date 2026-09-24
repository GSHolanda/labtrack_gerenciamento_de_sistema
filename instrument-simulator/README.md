# LabTrack — Instrument Simulator

Módulo **separado** do backend que simula equipamentos de laboratório
(pHmetro, HPLC, densímetro, Karl Fischer...) enviando resultados ao LabTrack
via API REST, como um driver de instrumento ou middleware de integração faria.
Não acessa o banco e não importa código do backend: só conhece o contrato HTTP.

```
┌──────────────────────┐   POST /api/v1/instruments/heartbeat  ┌──────────────┐
│ Instrument Simulator │ ────────────────────────────────────▶ │ LabTrack API │
│  (PH-METER-01 ...)   │   GET  /api/v1/instruments/worklist   │              │
│                      │ ────────────────────────────────────▶ │  valida,     │
│                      │   POST /api/v1/instruments/results    │  registra e  │
│                      │ ────────────────────────────────────▶ │  audita      │
└──────────────────────┘   Header: X-Instrument-Key            └──────────────┘
```

A cada ciclo, cada equipamento:

1. envia um **heartbeat** (atualiza "online" e "última comunicação");
2. consulta a **worklist**: testes pendentes, compatíveis com o seu tipo, em
   amostras em análise, das mais urgentes para as menos urgentes;
3. gera uma leitura na faixa central da especificação ou, com a probabilidade
   configurada, **fora da especificação (OOS)**, com as casas decimais do teste;
4. envia o resultado e mostra a classificação devolvida pela API, ou o código
   da recusa e o número da mensagem no log do equipamento.

Um equipamento em manutenção ou com calibração vencida recebe `409` na
worklist e não mede; o simulador informa o motivo e segue para o próximo.

## Instalação

```bash
cd instrument-simulator
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Configuração

Cada equipamento usa a **própria chave**, exibida uma única vez no cadastro
(`POST /api/v1/instruments`) ou na rotação (`POST /api/v1/instruments/{id}/rotate-key`).
O jeito mais simples de obter uma configuração pronta é gerar a demonstração:

```bash
cd backend
python -m app.cli seed-demo --simulator-config ../instrument-simulator/config.json
```

O formato está em [`config.example.json`](config.example.json):

```json
{
  "api_url": "http://localhost:8000/api/v1",
  "oos_rate": 0.1,
  "interval_seconds": 10,
  "instruments": [
    { "code": "PH-METER-01", "key": "lt_inst_..." },
    { "code": "HPLC-01", "key": "lt_inst_...", "oos_rate": 0.25 }
  ]
}
```

`config.json` contém segredos e está no `.gitignore`. Sem arquivo, as chaves
podem ir na linha de comando: `--api-url ... --key PH-METER-01=lt_inst_...`.

## Uso

```bash
# Todos os equipamentos, em ciclos de 10 s, até Ctrl+C
python -m simulator run

# Um ciclo, só o pHmetro, com 30% de leituras OOS e resultado reproduzível
python -m simulator run --once --instrument PH-METER-01 --oos-rate 0.3 --seed 42

# Vários equipamentos, 5 ciclos a cada 2 s, no máximo 3 envios por ciclo
python -m simulator run --cycles 5 --interval 2 --max-results 3 \
    --instrument HPLC-01 --instrument KF-01

# O que está pendente para cada equipamento
python -m simulator worklist

# Envio manual, útil para demonstrar as recusas (RN-19 a RN-24)
python -m simulator send --instrument PH-METER-01 --sample SMP-2026-0018 \
    --test PH --value 6.1 --unit mV                        # UNIT_MISMATCH
python -m simulator send --instrument PH-METER-01 --sample SMP-2026-0018 \
    --test PH --value 6.1 --unit pH --as-instrument X-9    # INSTRUMENT_ID_MISMATCH

# Estado de cada equipamento (ativo, calibração, pode medir)
python -m simulator heartbeat
```

Exemplo de saída:

```
Simulando PH-METER-01, PH-METER-02, DENS-01, KF-01, HPLC-01, VISC-01 em http://localhost:8000/api/v1 (OOS: 30%)
[PH-METER-01] SMP-2026-0018 PH = 5.04 pH: IN_SPEC
[PH-METER-01] SMP-2026-0019 PH = 5.37 pH: OOS  << OOS
[PH-METER-02] conectado, mas sem liberar medições (MAINTENANCE)
[PH-METER-02] worklist indisponível: INSTRUMENT_NOT_ACTIVE: O equipamento PH-METER-02 não está ativo (status: MAINTENANCE).
[DENS-01] SMP-2026-0018 DENSITY = 1.007 g/mL: IN_SPEC
[KF-01] SMP-2026-0017 MOISTURE = 3.87 %: OOS  << OOS
[HPLC-01] SMP-2026-0017 ASSAY = 101.3 %: IN_SPEC
[VISC-01] conectado, mas sem liberar medições (calibração vencida)
[VISC-01] worklist indisponível: CALIBRATION_EXPIRED: A calibração do equipamento VISC-01 venceu em 12/09/2026.
Resumo: 6 aceitos (3 OOS), 0 recusados.
```

Os códigos de saída são `0` (sucesso), `1` (a API recusou algo em `send`,
`worklist` ou `heartbeat`) e `2` (erro de configuração).

## Testes

```bash
pytest          # unitários: leituras, configuração, cliente HTTP e ciclo
```

`tests/test_end_to_end.py` executa o simulador contra a API real, em processo
e com SQLite em memória, sobre os dados de demonstração. Ele roda quando o
backend está instalado no mesmo ambiente (`pip install -e ../backend`); caso
contrário, é pulado.
