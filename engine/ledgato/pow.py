"""Proof-of-work for the Ledgato ledger.

Each ledger entry is mined with a nonce so that

    sha256(payload + str(nonce))

begins with ``difficulty`` leading zero characters. This layers a computational
cost on top of the Ed25519 signature chain: to alter an entry an attacker must
re-sign it AND re-mine every block that follows the fork, making history
rewrites expensive rather than free.

Backward compatible: ``difficulty <= 0`` means "no proof-of-work" and always
verifies (legacy entries without a nonce still load and pass).
"""
from __future__ import annotations

from .crypto import sha256


def target(difficulty: int) -> str:
    """The prefix a valid block hash must begin with."""
    return "0" * max(0, int(difficulty))


def hash_block(payload: bytes, nonce: int) -> str:
    """The mined block hash for a payload + nonce."""
    return sha256(payload + str(nonce).encode())


def satisfies(payload: bytes, nonce: int, difficulty: int) -> bool:
    return hash_block(payload, nonce).startswith(target(difficulty))


def mine(
    payload: bytes,
    difficulty: int,
    start: int = 0,
    max_attempts: int = 20_000_000,
) -> tuple[int, str]:
    """Find a nonce whose block hash satisfies the difficulty target."""
    if difficulty <= 0:
        return 0, hash_block(payload, 0)
    tgt = target(difficulty)
    nonce = int(start)
    while nonce < max_attempts:
        h = sha256(payload + str(nonce).encode())
        if h.startswith(tgt):
            return nonce, h
        nonce += 1
    raise ValueError(f"failed to mine block at difficulty={difficulty} (target '{tgt}')")


def verify(payload: bytes, nonce: int, difficulty: int) -> bool:
    """Verify a block's proof-of-work. Legacy (difficulty<=0) always passes."""
    if difficulty <= 0:
        return True
    return satisfies(payload, nonce, difficulty)