from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
# Generate a private key for use in the exchange.
server_private_key = ec.generate_private_key(curve=ec.SECP384R1(), backend=default_backend())
# In a real handshake the peer is a remote client. For this
# example we'll generate another local private key though.
peer_private_key = ec.generate_private_key(curve=ec.SECP384R1(), backend=default_backend())
shared_key = server_private_key.exchange(ec.ECDH(), peer_private_key.public_key())
# Perform key derivation.
derived_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'handshake data',
                   backend=default_backend()).derive(shared_key)
# And now we can demonstrate that the handshake performed in the
# opposite direction gives the same final value
same_shared_key = peer_private_key.exchange(ec.ECDH(), server_private_key.public_key())
# Perform key derivation.
same_derived_key = HKDF( algorithm=hashes.SHA256(),length=32, salt=None, info=b'handshake data',
                         backend=default_backend()).derive(same_shared_key)
key = Fernet.generate_key()
f = Fernet(shared_key)
a = list(enumerate(10000))
text = f'Hello_World {a}'
print(text)
msg_crypted = f.encrypt(text.encode('utf-8'))


assert derived_key == same_derived_key
