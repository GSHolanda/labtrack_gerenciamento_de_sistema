"""Código de negócio da amostra: ``SMP-AAAA-NNNN`` (sequencial por ano, RN-01)."""

import re

PREFIX = "SMP"
_PATTERN = re.compile(rf"^{PREFIX}-(\d{{4}})-(\d{{4,}})$")


def format_sample_code(year: int, sequence: int) -> str:
    return f"{PREFIX}-{year}-{sequence:04d}"


def year_prefix(year: int) -> str:
    return f"{PREFIX}-{year}-"


def parse_sequence(code: str) -> int | None:
    match = _PATTERN.match(code)
    return int(match.group(2)) if match else None
