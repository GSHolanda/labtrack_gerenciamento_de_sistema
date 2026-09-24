"""Configuração do simulador: URL da API e chave de cada equipamento.

Exemplo em ``config.example.json``. O arquivo real contém as chaves de integração e
não deve ser versionado (``config.json`` está no ``.gitignore``).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class InstrumentConfig:
    code: str
    key: str
    oos_rate: float | None = None  # sobrescreve a taxa geral para este equipamento


@dataclass(frozen=True)
class SimulatorConfig:
    api_url: str
    instruments: list[InstrumentConfig] = field(default_factory=list)
    oos_rate: float = 0.1
    interval_seconds: float = 10.0

    def select(self, codes: list[str] | None) -> list[InstrumentConfig]:
        """Equipamentos pedidos na linha de comando (todos, se nenhum for informado)."""
        if not codes:
            return list(self.instruments)
        by_code = {item.code.upper(): item for item in self.instruments}
        missing = [code for code in codes if code.upper() not in by_code]
        if missing:
            raise ConfigError(f"Equipamentos sem chave na configuração: {', '.join(missing)}.")
        return [by_code[code.upper()] for code in codes]


def load_config(path: Path) -> SimulatorConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON inválido em {path}: {exc}") from exc
    return parse_config(raw)


def parse_config(raw: Any) -> SimulatorConfig:
    if not isinstance(raw, dict) or not isinstance(raw.get("api_url"), str):
        raise ConfigError("A configuração precisa de 'api_url'.")
    instruments = []
    for item in raw.get("instruments", []):
        if not isinstance(item, dict) or not item.get("code") or not item.get("key"):
            raise ConfigError("Cada equipamento precisa de 'code' e 'key'.")
        instruments.append(
            InstrumentConfig(
                code=str(item["code"]).upper(),
                key=str(item["key"]),
                oos_rate=_rate(item.get("oos_rate")),
            )
        )
    return SimulatorConfig(
        api_url=raw["api_url"],
        instruments=instruments,
        oos_rate=_rate(raw.get("oos_rate", 0.1)) or 0.0,
        interval_seconds=float(raw.get("interval_seconds", 10.0)),
    )


def parse_key_option(value: str) -> InstrumentConfig:
    """``--key PH-METER-01=lt_inst_...`` na linha de comando."""
    code, separator, key = value.partition("=")
    if not separator or not code or not key:
        raise ConfigError("Use --key CODIGO=CHAVE.")
    return InstrumentConfig(code=code.strip().upper(), key=key.strip())


def _rate(value: Any) -> float | None:
    if value is None:
        return None
    rate = float(value)
    if not 0 <= rate <= 1:
        raise ConfigError("A taxa de OOS deve estar entre 0 e 1.")
    return rate
