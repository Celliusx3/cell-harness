"""AES-256-GCM under a key scrypt derives from the encryption key, with a fresh salt and nonce."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32


def sealed(plaintext: str, *, encryption_key: str, record_id: str) -> str:
    """`plaintext` sealed for `record_id`: base64 of salt, nonce, then ciphertext with its tag."""
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    encrypted = AESGCM(_derived_key(encryption_key, salt)).encrypt(
        nonce, plaintext.encode(), record_id.encode()
    )
    return base64.b64encode(salt + nonce + encrypted).decode()


def unsealed(ciphertext: str, *, encryption_key: str, record_id: str) -> str:
    """The plaintext `sealed` was given for `record_id`; `InvalidTag` when the key or id differ."""
    raw = base64.b64decode(ciphertext, validate=True)
    salt, nonce = raw[:SALT_BYTES], raw[SALT_BYTES : SALT_BYTES + NONCE_BYTES]
    encrypted = raw[SALT_BYTES + NONCE_BYTES :]
    return (
        AESGCM(_derived_key(encryption_key, salt))
        .decrypt(nonce, encrypted, record_id.encode())
        .decode()
    )


def _derived_key(encryption_key: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=KEY_BYTES, n=2**14, r=8, p=1).derive(encryption_key.encode())
