"""Ed25519 signing for Ledgato attestations.

Each signed attestation proves the author (this Ledgato instance) produced a
given ledger entry. Combined with the hash-chained ledger this makes the
evidence tamper-evident: altering any entry breaks its signature and the chain.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class Signer:
    """Generates or loads an Ed25519 identity and signs/verifies blobs."""

    def __init__(self, private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self._private = private_key or ed25519.Ed25519PrivateKey.generate()
        self._public = self._private.public_key()

    # ---- key management ------------------------------------------------
    @classmethod
    def load(cls, key_dir: str | Path) -> "Signer":
        key_dir = Path(key_dir)
        pem = (key_dir / "ledgato_private.pem").read_bytes()
        private = serialization.load_pem_private_key(pem, password=None)
        return cls(private)

    def save(self, key_dir: str | Path) -> Path:
        key_dir = Path(key_dir)
        key_dir.mkdir(parents=True, exist_ok=True)
        pem = self._private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path = key_dir / "ledgato_private.pem"
        path.write_bytes(pem)
        return path

    # ---- signing -------------------------------------------------------
    def public_key_b64(self) -> str:
        return base64.b64encode(self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )).decode()

    def sign(self, message: bytes) -> str:
        sig = self._private.sign(message)
        return base64.b64encode(sig).decode()

    # ---- verification -------------------------------------------------
    @staticmethod
    def verify(public_key_b64: str, message: bytes, signature_b64: str) -> bool:
        try:
            pub_raw = base64.b64decode(public_key_b64)
            sig_raw = base64.b64decode(signature_b64)
            public = ed25519.Ed25519PublicKey.from_public_bytes(pub_raw)
            public.verify(sig_raw, message)
            return True
        except Exception:
            return False


def sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()