"""Linha de comando do simulador.

    python -m simulator run --config config.json                 # todos, até Ctrl+C
    python -m simulator run --once --oos-rate 0.3 --instrument PH-METER-01
    python -m simulator worklist --instrument HPLC-01
    python -m simulator send --instrument PH-METER-01 --sample SMP-2026-0018 \\
        --test PH --value 7.2 --unit pH
    python -m simulator heartbeat

Sem arquivo de configuração, informe ``--api-url`` e ``--key CODIGO=CHAVE``.
"""

import argparse
import random
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from simulator.client import ApiError, HttpClient, LabTrackClient
from simulator.config import (
    ConfigError,
    InstrumentConfig,
    SimulatorConfig,
    load_config,
    parse_key_option,
)
from simulator.runner import InstrumentSimulator, run

DEFAULT_API_URL = "http://localhost:8000/api/v1"


def main(argv: list[str] | None = None, *, http: HttpClient | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = _load(args)
        instruments = config.select(args.instrument)
        if not instruments:
            raise ConfigError("Nenhum equipamento configurado (use --config ou --key).")
    except ConfigError as error:
        print(f"Erro de configuração: {error}", file=sys.stderr)
        return 2

    def client_for(item: InstrumentConfig) -> LabTrackClient:
        return LabTrackClient(config.api_url, item.key, http=http)

    if args.command == "run":
        return _run(args, config, instruments, client_for)
    if args.command == "send":
        return _send(args, instruments, client_for)
    if args.command == "worklist":
        return _worklist(instruments, client_for)
    return _heartbeat(instruments, client_for)


def _run(args, config, instruments, client_for) -> int:  # type: ignore[no-untyped-def]
    rng = random.Random(args.seed)
    general_rate = args.oos_rate if args.oos_rate is not None else config.oos_rate
    simulators = [
        InstrumentSimulator(
            item.code,
            client_for(item),
            oos_rate=item.oos_rate if item.oos_rate is not None else general_rate,
            rng=rng,
            max_results=args.max_results,
        )
        for item in instruments
    ]
    cycles = 1 if args.once else args.cycles
    interval = args.interval if args.interval is not None else config.interval_seconds
    codes = ", ".join(item.code for item in instruments)
    print(f"Simulando {codes} em {config.api_url} (OOS: {general_rate:.0%})")
    try:
        reports = run(simulators, cycles=cycles, interval=interval)
    except KeyboardInterrupt:
        print("\nSimulação interrompida.")
        return 0
    accepted = sum(report.accepted for report in reports)
    oos = sum(report.oos for report in reports)
    rejected = sum(len(report.rejected) for report in reports)
    print(f"Resumo: {accepted} aceitos ({oos} OOS), {rejected} recusados.")
    return 0


def _send(args, instruments, client_for) -> int:  # type: ignore[no-untyped-def]
    if len(instruments) != 1:
        print("Informe exatamente um --instrument para 'send'.", file=sys.stderr)
        return 2
    item = instruments[0]
    code = args.as_instrument or item.code
    try:
        response = client_for(item).submit_result(
            code, args.sample, args.test, args.value, args.unit
        )
    except ApiError as error:
        print(f"Recusado: {error.code} (HTTP {error.status_code}): {error.message}")
        if error.message_id:
            print(f"Registrado no log do equipamento como mensagem {error.message_id}.")
        return 1
    print(
        f"Aceito: mensagem {response['message_id']}, resultado {response['result']} "
        f"{response['unit']}: {response['spec_status']}"
    )
    return 0


def _worklist(instruments, client_for) -> int:  # type: ignore[no-untyped-def]
    status = 0
    for item in instruments:
        try:
            worklist = client_for(item).worklist()
        except ApiError as error:
            print(f"[{item.code}] {error.code}: {error.message}")
            status = 1
            continue
        print(f"[{item.code}] {len(worklist['items'])} teste(s) pendente(s)")
        for entry in worklist["items"]:
            low, high = (
                _limit(entry[side], entry["decimal_places"]) for side in ("spec_min", "spec_max")
            )
            limits = f"{low} a {high} {entry['unit']}"
            print(f"  {entry['priority']:<7} {entry['sample_code']}  {entry['test']:<12} {limits}")
    return status


def _heartbeat(instruments, client_for) -> int:  # type: ignore[no-untyped-def]
    status = 0
    for item in instruments:
        try:
            state = client_for(item).heartbeat(item.code)
        except ApiError as error:
            print(f"[{item.code}] {error.code}: {error.message}")
            status = 1
            continue
        ready = "pode medir" if state["can_measure"] else "não pode medir"
        print(
            f"[{item.code}] {state['status']}, calibração até "
            f"{state['calibration_due_date']}: {ready}"
        )
    return status


def _load(args: argparse.Namespace) -> SimulatorConfig:
    keys = [parse_key_option(value) for value in args.key or []]
    if args.config.exists():
        config = load_config(args.config)
    elif keys:
        config = SimulatorConfig(api_url=DEFAULT_API_URL)
    else:
        raise ConfigError(
            f"{args.config} não encontrado. Gere-o com 'python -m app.cli seed-demo'."
        )
    by_code = {item.code: item for item in config.instruments}
    by_code.update({item.code: item for item in keys})
    return SimulatorConfig(
        api_url=args.api_url or config.api_url,
        instruments=list(by_code.values()),
        oos_rate=config.oos_rate,
        interval_seconds=config.interval_seconds,
    )


def _limit(value: str | None, places: int) -> str:
    return f"{Decimal(value):.{places}f}" if value is not None else "-"


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"valor numérico inválido: {value}") from exc


def _rate(value: str) -> float:
    rate = float(value)
    if not 0 <= rate <= 1:
        raise argparse.ArgumentTypeError("use um valor entre 0 e 1")
    return rate


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, default=Path("config.json"))
    common.add_argument("--api-url", help=f"Sobrescreve a URL da configuração ({DEFAULT_API_URL})")
    common.add_argument("--key", action="append", metavar="CODIGO=CHAVE")
    common.add_argument(
        "--instrument", action="append", metavar="CODIGO", help="Repita para vários"
    )

    parser = argparse.ArgumentParser(
        prog="python -m simulator", description="Simulador de equipamentos do LabTrack"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_cmd = commands.add_parser("run", parents=[common], help="Mede a worklist em ciclos")
    repeat = run_cmd.add_mutually_exclusive_group()
    repeat.add_argument("--once", action="store_true", help="Um único ciclo")
    repeat.add_argument("--cycles", type=int, help="Quantidade de ciclos (padrão: até Ctrl+C)")
    run_cmd.add_argument("--interval", type=float, help="Segundos entre ciclos")
    run_cmd.add_argument("--oos-rate", type=_rate, help="Probabilidade de leitura OOS (0 a 1)")
    run_cmd.add_argument("--max-results", type=int, help="Máximo de envios por ciclo")
    run_cmd.add_argument("--seed", type=int, help="Semente para leituras reproduzíveis")

    send = commands.add_parser("send", parents=[common], help="Envia uma leitura específica")
    send.add_argument("--sample", required=True)
    send.add_argument("--test", required=True)
    send.add_argument("--value", required=True, type=_decimal)
    send.add_argument("--unit", required=True)
    send.add_argument(
        "--as-instrument",
        metavar="CODIGO",
        help="instrument_id enviado no corpo (para demonstrar INSTRUMENT_ID_MISMATCH)",
    )

    commands.add_parser("worklist", parents=[common], help="Mostra os testes pendentes")
    commands.add_parser("heartbeat", parents=[common], help="Sinaliza que está conectado")
    return parser


if __name__ == "__main__":
    sys.exit(main())
