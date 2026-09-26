"""x402 payment adapter for governed machine-to-machine purchases.

The wallet credential belongs to the Ledgato gateway. Agents submit an
x402.pay action; the gateway performs policy / grant / approval checks before
this adapter can reach the payment-capable HTTP client.

The optional x402 dependency is imported only by from_evm_private_key so
installations that do not use payments keep the existing dependency surface.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from .base import ExecutionReceipt
from ..models import Action

PAYMENT_TOOL = "x402.pay"

# Headers that would let a caller inject credentials, a prebuilt payment, or
# alter hop-by-hop request semantics. The x402 SDK owns payment headers.
_BLOCKED_HEADERS = {
    "authorization",
    "cookie",
    "host",
    "proxy-authorization",
    "connection",
    "transfer-encoding",
    "payment-required",
    "payment-response",
    "payment-signature",
    "x-payment",
    "x-payment-response",
}


class X402PaymentClient(Protocol):
    """Minimal transport contract used by the adapter and its tests."""

    def request(
        self,
        *,
        method: str,
        url: str,
        params: Mapping[str, Any] | None,
        json_body: Any,
        headers: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


class X402Adapter:
    """Execute x402 payments only after Ledgato has returned ALLOW."""

    name = "x402"

    def __init__(
        self,
        *,
        client: X402PaymentClient,
        allowed_hosts: Sequence[str],
        allow_http: bool = False,
        live_provider: bool = True,
    ):
        hosts = {_normalize_host(host) for host in allowed_hosts if str(host).strip()}
        if not hosts:
            raise ValueError("x402 adapter requires at least one allowed host")
        self.client = client
        self.allowed_hosts = hosts
        self.allow_http = bool(allow_http)
        self.is_live_provider = bool(live_provider)
        self.boundary_resource = next(iter(hosts)) if len(hosts) == 1 else None

    @classmethod
    def from_evm_private_key(
        cls,
        *,
        private_key: str,
        allowed_hosts: Sequence[str],
        networks: Sequence[str],
        max_amount_per_payment: str = "$0.10",
        timeout_seconds: float = 30.0,
    ) -> "X402Adapter":
        """Build the official x402 sync client behind a hard spend cap.

        networks is required intentionally. The caller must opt into the exact
        EVM networks on which this wallet is allowed to sign.
        """
        if not private_key:
            raise ValueError("x402 private key is required")
        normalized_networks = [str(network).strip() for network in networks if str(network).strip()]
        if not normalized_networks:
            raise ValueError("x402 adapter requires at least one explicit network")
        try:
            client = _RequestsX402PaymentClient(
                private_key=private_key,
                networks=normalized_networks,
                max_amount_per_payment=max_amount_per_payment,
                timeout_seconds=timeout_seconds,
            )
        except ImportError as exc:
            raise RuntimeError(
                "x402 support is optional; install Ledgato with the 'x402' extra"
            ) from exc
        return cls(client=client, allowed_hosts=allowed_hosts)

    def discover(self, agent: str) -> set[str]:
        # Presence of this adapter means a payment-capable client was explicitly
        # configured. Balance / merchant availability is evaluated at execution.
        return {PAYMENT_TOOL}

    def execute(self, action: Action) -> ExecutionReceipt:
        if action.tool != PAYMENT_TOOL:
            raise ValueError(f"unsupported x402 action '{action.tool}'")

        method = str(action.params.get("method", "GET")).upper()
        if method not in {"GET", "POST"}:
            raise ValueError("x402 adapter currently supports GET and POST only")

        url = str(action.params.get("url", "")).strip()
        host = self._validate_url(url)
        headers = _validated_headers(action.params.get("headers"))
        params = action.params.get("params")
        if params is not None and not isinstance(params, Mapping):
            raise ValueError("x402 params must be an object")

        result = dict(
            self.client.request(
                method=method,
                url=url,
                params=dict(params) if params is not None else None,
                json_body=action.params.get("json"),
                headers=headers,
            )
        )

        status_code = _required_status(result)
        if not 200 <= status_code < 300:
            raise RuntimeError(f"x402 resource returned HTTP {status_code}")

        settlement = result.get("settlement")
        if not isinstance(settlement, Mapping) or settlement.get("success") is not True:
            raise RuntimeError(
                "x402 request completed without successful settlement evidence"
            )

        transaction = settlement.get("transaction")
        receipt_result = {
            "url": str(result.get("url") or url),
            "host": host,
            "method": method,
            "status_code": status_code,
            "content_type": result.get("content_type"),
            "body": result.get("body"),
            "settlement": dict(settlement),
            "payment_response_header_sha256": result.get(
                "payment_response_header_sha256"
            ),
        }
        return ExecutionReceipt(
            adapter=self.name,
            action=action.tool,
            executed=True,
            status="settled",
            external_id=str(transaction) if transaction else None,
            result=receipt_result,
        )

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        settlement = receipt.result.get("settlement")
        if not isinstance(settlement, Mapping):
            return {
                "verified": False,
                "method": "x402_settlement_response",
                "reason": "missing settlement response",
            }

        status_code = receipt.result.get("status_code")
        transaction = settlement.get("transaction")
        tx_matches = (
            receipt.external_id is None
            or transaction is None
            or str(receipt.external_id) == str(transaction)
        )
        verified = (
            settlement.get("success") is True
            and isinstance(status_code, int)
            and 200 <= status_code < 300
            and bool(receipt.result.get("payment_response_header_sha256"))
            and tx_matches
        )
        return {
            "verified": verified,
            "method": "x402_settlement_response",
            "settlement_success": settlement.get("success") is True,
            "transaction": transaction,
            "network": settlement.get("network"),
            "payment_response_header_sha256": receipt.result.get(
                "payment_response_header_sha256"
            ),
            "transaction_matches_receipt": tx_matches,
            # This verifies the provider's x402 settlement response. It does not
            # independently establish chain finality.
            "onchain_finality_verified": False,
        }

    def verify_denied(self, action: Action) -> dict[str, Any]:
        return {
            "verified": True,
            "method": "gateway_non_execution_receipt",
            "executed": False,
            "note": "Gateway did not invoke the x402 payment client for this denied action.",
        }

    def _validate_url(self, url: str) -> str:
        if not url:
            raise ValueError("x402 action requires a url")
        parsed = urlsplit(url)
        allowed_schemes = {"https"} | ({"http"} if self.allow_http else set())
        if parsed.scheme.lower() not in allowed_schemes:
            raise ValueError("x402 resource must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("x402 resource URL must not contain user info")
        if not parsed.hostname:
            raise ValueError("x402 resource URL has no hostname")
        host = _normalize_host(parsed.hostname)
        if host not in self.allowed_hosts:
            raise ValueError(f"x402 host '{host}' is not allowlisted")
        return host


class _RequestsX402PaymentClient:
    """Official x402 requests client wrapped in a tiny serializable interface."""

    def __init__(
        self,
        *,
        private_key: str,
        networks: Sequence[str],
        max_amount_per_payment: str,
        timeout_seconds: float,
    ):
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http import x402HTTPClientSync
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client

        account = Account.from_key(private_key)
        payment_client = x402ClientSync().set_spend_controls(
            {"max_amount_per_payment": max_amount_per_payment}
        )
        register_exact_evm_client(
            payment_client,
            EthAccountSigner(account),
            networks=list(networks),
        )
        self._client = payment_client
        self._http_client = x402HTTPClientSync(payment_client)
        self._timeout_seconds = float(timeout_seconds)

    def request(
        self,
        *,
        method: str,
        url: str,
        params: Mapping[str, Any] | None,
        json_body: Any,
        headers: Mapping[str, str],
    ) -> Mapping[str, Any]:
        from x402.http.clients import x402_requests

        with x402_requests(self._client) as session:
            response = session.request(
                method,
                url,
                params=dict(params) if params is not None else None,
                json=json_body,
                headers=dict(headers),
                timeout=self._timeout_seconds,
                allow_redirects=False,
            )

            settlement: dict[str, Any] | None = None
            try:
                parsed = self._http_client.get_payment_settle_response(
                    lambda name: response.headers.get(name)
                )
                settlement = _model_to_dict(parsed)
            except ValueError:
                settlement = None

            payment_header = (
                response.headers.get("PAYMENT-RESPONSE")
                or response.headers.get("X-PAYMENT-RESPONSE")
            )
            payment_header_hash = (
                hashlib.sha256(payment_header.encode()).hexdigest()
                if payment_header
                else None
            )

            content_type = response.headers.get("content-type")
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            return {
                "status_code": int(response.status_code),
                "url": str(response.url),
                "content_type": content_type,
                "body": body,
                "settlement": settlement,
                "payment_response_header_sha256": payment_header_hash,
            }


def _required_status(result: Mapping[str, Any]) -> int:
    status = result.get("status_code")
    if isinstance(status, bool):
        raise ValueError("x402 response status_code is invalid")
    try:
        return int(status)
    except (TypeError, ValueError) as exc:
        raise ValueError("x402 response has no valid status_code") from exc


def _validated_headers(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("x402 headers must be an object")
    cleaned: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        name = str(raw_name).strip()
        lowered = name.lower()
        if not name:
            raise ValueError("x402 header name must not be empty")
        if lowered in _BLOCKED_HEADERS or lowered.startswith("payment-"):
            raise ValueError(f"x402 caller may not set protected header '{name}'")
        cleaned[name] = str(raw_value)
    return cleaned


def _normalize_host(host: str) -> str:
    value = str(host).strip().lower().rstrip(".")
    if not value:
        raise ValueError("x402 host must not be empty")
    # Admin configuration is host-only so ports cannot accidentally become part
    # of the authorization boundary.
    if "://" in value or "/" in value or ":" in value:
        raise ValueError("x402 allowed_hosts entries must be hostnames without scheme, path, or port")
    return value


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return dict(model.model_dump())
    if hasattr(model, "dict"):
        return dict(model.dict())
    if isinstance(model, Mapping):
        return dict(model)
    # Last-resort serialization guard for SDK model changes.
    return json.loads(json.dumps(model, default=str))
