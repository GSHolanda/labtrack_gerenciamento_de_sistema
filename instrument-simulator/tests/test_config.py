import json
from pathlib import Path

import pytest

from simulator.config import ConfigError, load_config, parse_config, parse_key_option


def test_loads_instruments_and_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "api_url": "http://localhost:8000/api/v1",
                "instruments": [
                    {"code": "ph-meter-01", "key": "lt_inst_a"},
                    {"code": "HPLC-01", "key": "lt_inst_b", "oos_rate": 0.5},
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.api_url == "http://localhost:8000/api/v1"
    assert (config.oos_rate, config.interval_seconds) == (0.1, 10.0)
    assert [(i.code, i.key, i.oos_rate) for i in config.instruments] == [
        ("PH-METER-01", "lt_inst_a", None),
        ("HPLC-01", "lt_inst_b", 0.5),
    ]
    assert [i.code for i in config.select(["hplc-01"])] == ["HPLC-01"]
    assert len(config.select(None)) == 2
    with pytest.raises(ConfigError, match="KF-01"):
        config.select(["KF-01"])


def test_example_config_is_valid() -> None:
    example = Path(__file__).resolve().parents[1] / "config.example.json"
    assert load_config(example).instruments


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {"instruments": []},
        {"api_url": "http://x", "instruments": [{"code": "PH"}]},
        {"api_url": "http://x", "oos_rate": 1.5},
        {"api_url": "http://x", "instruments": [{"code": "PH", "key": "k", "oos_rate": -1}]},
    ],
)
def test_invalid_config_is_refused(raw: object) -> None:
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_missing_or_malformed_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="não encontrado"):
        load_config(tmp_path / "config.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON inválido"):
        load_config(broken)


def test_key_option() -> None:
    option = parse_key_option("ph-meter-01=lt_inst_abc")
    assert (option.code, option.key) == ("PH-METER-01", "lt_inst_abc")
    with pytest.raises(ConfigError):
        parse_key_option("PH-METER-01")
