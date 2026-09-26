"""Ledgato — agent assurance and enforceable authority boundaries."""

from .approvals import Approval, ApprovalStore
from .authority import AuthorityStore
from .campaign import (
    CampaignAuthority,
    CampaignAuthorityStore,
    CampaignError,
    authorize_campaign_action,
    build_authority,
    canonical_digest,
)
from .engine import ALLOW, APPROVE, DENY, Decision, detect_drift, evaluate_action
from .gate import GateResult, attest_release
from .gateway import EnforcementGateway
from .ledger import Ledger, LedgerEntry
from .models import Action, AuthorityGrant, Policy, load_policies, parse_policy
from .probes import run_probes, summarize
from .sdk import LedgatoClient, LedgatoError
from .principals import (
    Principal,
    PrincipalRegistry,
    TRUST_OPERATIONAL,
    TRUST_ADVERSARIAL,
    TRUST_VERIFIER,
    ROLE_VERIFIER,
)

__version__ = "0.3.0"
__all__ = [
    "Action",
    "AuthorityGrant",
    "Policy",
    "Ledger",
    "LedgerEntry",
    "Decision",
    "ALLOW",
    "DENY",
    "APPROVE",
    "GateResult",
    "AuthorityStore",
    "CampaignAuthority",
    "CampaignAuthorityStore",
    "CampaignError",
    "authorize_campaign_action",
    "build_authority",
    "canonical_digest",
    "Principal",
    "PrincipalRegistry",
    "TRUST_OPERATIONAL",
    "TRUST_ADVERSARIAL",
    "TRUST_VERIFIER",
    "ROLE_VERIFIER",
    "Approval",
    "ApprovalStore",
    "EnforcementGateway",
    "LedgatoClient",
    "LedgatoError",
    "attest_release",
    "detect_drift",
    "evaluate_action",
    "load_policies",
    "parse_policy",
    "run_probes",
    "summarize",
    "__version__",
]
