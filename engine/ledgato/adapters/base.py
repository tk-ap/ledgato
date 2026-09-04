"""Adapter contract for systems protected by the Ledgato gateway."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from ..models import Action


@dataclass
class ExecutionReceipt:
    adapter: str
    action: str
    executed: bool
    status: str
    external_id: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnforcementAdapter(Protocol):
    """A downstream system that can only be reached through the gateway.

    Real enforcement depends on deployment: the protected credential/token must
    live with this adapter/gateway, not remain directly available to the agent.
    """

    name: str

    def discover(self, agent: str) -> set[str]:
        """Return capabilities currently reachable through this adapter."""

    def execute(self, action: Action) -> ExecutionReceipt:
        """Perform an already-authorized action."""

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        """Read the downstream system after execution and return evidence."""

    def verify_denied(self, action: Action) -> dict[str, Any]:
        """Read downstream state without executing the denied action."""
