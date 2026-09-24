"""Cliente HTTP de um equipamento: conhece só a API REST e a própria chave."""

from decimal import Decimal
from typing import Any, Protocol

import httpx


class HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class HttpClient(Protocol):
    """O mínimo que o simulador usa de um cliente HTTP (httpx ou o TestClient da API)."""

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...


class ApiError(Exception):
    """Resposta de erro da API, com o código estável do envelope ``{"error": {...}}``."""

    def __init__(
        self, status_code: int, code: str, message: str, details: Any | None = None
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details

    @classmethod
    def from_response(cls, response: HttpResponse) -> "ApiError":
        try:
            error = response.json()["error"]
            return cls(response.status_code, error["code"], error["message"], error.get("details"))
        except (ValueError, KeyError, TypeError):
            return cls(response.status_code, f"HTTP_{response.status_code}", response.text[:200])

    @property
    def message_id(self) -> int | None:
        """Identificador da mensagem recusada no log do equipamento (RN-24)."""
        return self.details.get("message_id") if isinstance(self.details, dict) else None


class LabTrackClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        http: HttpClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.headers = {"X-Instrument-Key": api_key}
        self._owns_http = http is None
        self.http: HttpClient = http or httpx.Client(timeout=timeout)

    def worklist(self, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/instruments/worklist", params={"limit": limit})

    def submit_result(
        self, instrument_id: str, sample_code: str, test: str, result: Decimal, unit: str
    ) -> dict[str, Any]:
        payload = {
            "instrument_id": instrument_id,
            "sample_code": sample_code,
            "test": test,
            "result": str(result),  # texto: o valor chega exato, sem arredondamento de float
            "unit": unit,
        }
        return self._request("POST", "/instruments/results", json=payload)

    def heartbeat(self, instrument_id: str) -> dict[str, Any]:
        return self._request(
            "POST", "/instruments/heartbeat", json={"instrument_id": instrument_id}
        )

    def close(self) -> None:
        if self._owns_http and isinstance(self.http, httpx.Client):
            self.http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.http.request(
                method, f"{self.base_url}{path}", headers=self.headers, **kwargs
            )
        except httpx.HTTPError as exc:
            raise ApiError(0, "CONNECTION_ERROR", f"API indisponível: {exc}") from exc
        if response.status_code >= 400:
            raise ApiError.from_response(response)
        return response.json()
