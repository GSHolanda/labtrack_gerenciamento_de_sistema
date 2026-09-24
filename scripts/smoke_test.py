"""Smoke test da stack Docker: roda contra a interface publicada (Nginx).

    python scripts/smoke_test.py [--base-url http://localhost:8080] [--wait-simulator 120]

Confere o Nginx (SPA, cabeçalhos, proxy da API e do Swagger), a API com os dados
de demonstração (login, amostras, relatório em PDF, cadeia do audit trail) e o
simulador enviando resultados. Só usa a biblioteca padrão.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from email.message import Message
from typing import Any

DEMO_PASSWORD = "Demo@2026"


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.token: str | None = None
        self.checks = 0

    def request(
        self, path: str, *, data: bytes | None = None, headers: dict[str, str] | None = None
    ) -> tuple[int, Message, bytes]:
        """Status, cabeçalhos (sem diferenciar maiúsculas) e corpo."""
        all_headers = dict(headers or {})
        if self.token:
            all_headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=all_headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def json(self, path: str) -> Any:
        status, _, body = self.request(path)
        self.expect(status == 200, f"GET {path} -> {status}: {body[:200]!r}")
        return json.loads(body)

    def expect(self, condition: bool, message: str) -> None:
        if not condition:
            raise SystemExit(f"FALHOU: {message}")
        self.checks += 1

    def ok(self, message: str) -> None:
        print(f"  ok  {message}")


def run(base_url: str, wait_simulator: int) -> None:
    smoke = Smoke(base_url)
    started = datetime.now(UTC)
    print(f"Smoke test em {smoke.base}")

    status, headers, body = smoke.request("/healthz")
    smoke.expect(status == 200, f"/healthz -> {status}")
    status, headers, body = smoke.request("/")
    smoke.expect(status == 200 and b'id="root"' in body, "index.html da interface")
    smoke.expect(headers.get("X-Content-Type-Options") == "nosniff", "cabeçalhos de segurança")
    status, _, body = smoke.request("/samples/1")
    smoke.expect(status == 200 and b'id="root"' in body, "rota da SPA volta para o index")
    smoke.ok("Nginx: interface, rotas da SPA e cabeçalhos de segurança")

    ready = smoke.json("/api/v1/health/ready")
    smoke.expect(ready["status"] == "ready", f"readiness: {ready}")
    status, _, body = smoke.request("/docs")
    smoke.expect(status == 200 and b"swagger" in body.lower(), "Swagger pelo proxy")
    smoke.ok("API pronta (banco conectado) e Swagger em /docs")

    form = urllib.parse.urlencode({"username": "ana.souza", "password": DEMO_PASSWORD})
    status, _, body = smoke.request(
        "/api/v1/auth/login",
        data=form.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    smoke.expect(status == 200, f"login da demonstração -> {status}: {body[:200]!r}")
    smoke.token = json.loads(body)["access_token"]
    smoke.ok("login com usuário da demonstração")

    samples = smoke.json("/api/v1/samples?size=100")
    smoke.expect(samples["total"] >= 20, f"amostras da demonstração: {samples['total']}")
    approved = next(item for item in samples["items"] if item["status"] == "APPROVED")
    status, headers, body = smoke.request(f"/api/v1/reports/samples/{approved['id']}/pdf")
    smoke.expect(status == 200 and body.startswith(b"%PDF"), f"PDF do relatório -> {status}")
    smoke.expect(len(headers.get("X-Report-SHA256", "")) == 64, "impressão digital do PDF")
    smoke.ok(f"{samples['total']} amostras; relatório de {approved['sample_code']} em PDF")

    verification = smoke.json("/api/v1/audit-logs/verify")
    smoke.expect(verification["valid"] is True, f"cadeia do audit trail: {verification}")
    smoke.ok(f"audit trail íntegro ({verification['checked_records']} registros)")

    since = (started - timedelta(minutes=5)).isoformat()
    query = urllib.parse.urlencode(
        {"source": "INSTRUMENT", "current_only": "false", "entered_from": since}
    )
    deadline = time.monotonic() + wait_simulator
    total = 0
    while time.monotonic() < deadline:
        total = smoke.json(f"/api/v1/results?{query}")["total"]
        if total:
            break
        time.sleep(5)
    smoke.expect(total > 0, f"nenhum resultado do simulador em {wait_simulator}s")
    smoke.ok(f"simulador enviou {total} resultado(s) pela API REST")

    print(f"Smoke test aprovado: {smoke.checks} verificações.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--wait-simulator", type=int, default=120, help="segundos")
    args = parser.parse_args(argv)
    run(args.base_url, args.wait_simulator)
    return 0


if __name__ == "__main__":
    sys.exit(main())
