from cryptography.fernet import Fernet


import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

password = Fernet.generate_key()
salt = Fernet.generate_key()

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=100000,
    backend=default_backend()
)
session_key = base64.urlsafe_b64encode(kdf.derive(password))
fernet: Fernet = Fernet(b'')