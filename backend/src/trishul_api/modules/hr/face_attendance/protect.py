"""Encryption and storage of face data: AES-256-GCM for face vectors and photos.

The key is 32 random bytes, base64-encoded, read from Secrets Manager (TRISHUL_FACE_DATA_KEY_SECRET_ID)
or, for local development, TRISHUL_FACE_DATA_KEY. Without a key, face registration is switched off
rather than storing biometric data in the clear. Photos sit under backend/var/attachments/faces
(the same disk area as other documents until an S3 bucket exists); only this module touches them.
"""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from trishul_api.config import Settings
from trishul_api.modules.hr.face_attendance.engine import VECTOR_SIZE, FloatVector
from trishul_api.secrets import SecretError, SecretProvider

_ROOT = Path(__file__).resolve().parents[5] / "var" / "attachments"
_NONCE = 12
_VERSION = b"\x01"


class FaceDataKeyMissing(RuntimeError):
    """No face-data key is configured, so face data cannot be stored or read."""


def load_key(settings: Settings, secrets: SecretProvider | None) -> bytes:
    raw: str | None = None
    if settings.face_data_key_secret_id:
        if secrets is None:
            raise FaceDataKeyMissing("Secrets Manager is not available for the face-data key.")
        try:
            raw = secrets.get_string(settings.face_data_key_secret_id)
        except SecretError as error:
            raise FaceDataKeyMissing(str(error)) from error
    elif settings.face_data_key is not None:
        raw = settings.face_data_key.get_secret_value()
    if not raw:
        raise FaceDataKeyMissing("The face-data encryption key is not configured.")
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError) as error:
        raise FaceDataKeyMissing("The face-data key is not valid base64.") from error
    if len(key) != 32:
        raise FaceDataKeyMissing("The face-data key must be 32 bytes (AES-256).")
    return key


class FaceVault:
    """Encrypts, stores and reads face vectors and photos with one key."""

    def __init__(self, key: bytes, root: Path | None = None) -> None:
        self._aead = AESGCM(key)
        self._root = (root or _ROOT).resolve()

    # vectors ------------------------------------------------------------------------

    def seal_vector(self, vector: FloatVector) -> bytes:
        return self._seal(np.asarray(vector, dtype="<f4").tobytes(), b"face-vector")

    def open_vector(self, sealed: bytes) -> FloatVector:
        data = self._open(sealed, b"face-vector")
        vector = np.frombuffer(data, dtype="<f4").astype(np.float32)
        if vector.size != VECTOR_SIZE:
            raise ValueError("Stored face vector has the wrong size.")
        return vector

    # photos -------------------------------------------------------------------------

    def store_photo(self, folder: str, owner_id: int, jpeg: bytes) -> str:
        key = f"faces/{folder}/{owner_id}/{uuid4().hex}.jpg.enc"
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self._seal(jpeg, b"face-photo"))
        return key

    def read_photo(self, key: str) -> bytes | None:
        path = (self._root / key).resolve()
        if self._root not in path.parents or not path.is_file():
            return None
        return self._open(path.read_bytes(), b"face-photo")

    def remove_photo(self, key: str) -> None:
        path = (self._root / key).resolve()
        if self._root in path.parents and path.is_file():
            path.unlink()

    # ---------------------------------------------------------------------------------

    def _seal(self, data: bytes, purpose: bytes) -> bytes:
        nonce = os.urandom(_NONCE)
        return _VERSION + nonce + self._aead.encrypt(nonce, data, purpose)

    def _open(self, sealed: bytes, purpose: bytes) -> bytes:
        if not sealed.startswith(_VERSION) or len(sealed) <= 1 + _NONCE:
            raise ValueError("Unknown face-data format.")
        nonce = sealed[1 : 1 + _NONCE]
        return self._aead.decrypt(nonce, sealed[1 + _NONCE :], purpose)
