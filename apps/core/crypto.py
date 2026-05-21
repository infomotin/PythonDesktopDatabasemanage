import uuid
from contextlib import contextmanager

from cryptography.fernet import Fernet

from config.settings import ENCRYPTION_KEY


class EncryptionManager:
    def __init__(self, key: str = None):
        if key is None:
            key = ENCRYPTION_KEY
        if isinstance(key, str):
            key = key.encode()
        try:
            self.cipher = Fernet(key)
        except Exception:
            key = Fernet.generate_key()
            self.cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        if not data:
            return ""
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to encrypt data: {e}")

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()


encryption_manager = EncryptionManager()


def encrypt_credential(value: str) -> str:
    return encryption_manager.encrypt(value)


def decrypt_credential(encrypted_value: str) -> str:
    return encryption_manager.decrypt(encrypted_value)
