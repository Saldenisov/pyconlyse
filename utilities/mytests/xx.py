from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

# Working RSA encryption you can run for yourself
MESSAGE = 'I am a very secret message'.encode('utf-8')

# Create private key
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

# Create public key
public_key = private_key.public_key()
pub_key_bytes = private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
public_key = load_pem_public_key(pub_key_bytes,backend=default_backend())

# Encrypt
ciphertext = public_key.encrypt(
    MESSAGE,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA1()),
        algorithm=hashes.SHA1(),
        label=None
    )
)

# Encrypted text
print(ciphertext)

# Decrypt
plaintext = private_key.decrypt(
    ciphertext,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA1()),
        algorithm=hashes.SHA1(),
        label=None
    )
)

# Decrypted text
print(plaintext)

# Print human readable key
pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption())

pem_data = pem.splitlines()
print(pem)

from cryptography.hazmat.primitives.serialization import load_pem_private_key
private_key = load_pem_private_key(pem, None, default_backend())

# Decrypt
plaintext = private_key.decrypt(
    ciphertext,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA1()),
        algorithm=hashes.SHA1(),
        label=None
    )
)

# Decrypted text
print(plaintext)




from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization



def gen_key():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    return private_key


def save_key(pk, filename):
    pem = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(filename, 'wb') as pem_out:
        pem_out.write(pem)


def save_key_bad(pk, filename):
    pem = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    pem_data = pem.splitlines()
    with open(filename, 'wb') as pem_out:
        for line in pem_data:
            pem_out.write(line)


def load_key(filename):
    with open(filename, 'rb') as pem_in:
        pemlines = pem_in.read()
    private_key = load_pem_private_key(pemlines, None, default_backend())
    return private_key


if __name__ == '__main__':
    pk = gen_key()
    filename = 'privkey.pem'
    save_key(pk, filename)
    pk2 = load_key(filename)
    server_pub_key=b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArp8Sl+X9tgrXxGuTk+IJ\naSTsLFwLmY4rCz96i6ziuA1fd1DjaN2aUeXScosTjn6kNrQCb+fFStA941+k7AdB\n1QKsUJX6/zdvIzDwLwt7fFulXgWgtLFeqiQNo4jg9pdi7zIB1ztQVGbqxArINMY0\nrsEYd0fWIec9zWliUW+cmGB8xjjPu/LtoDt8ZuQLBh9DuGNUdBzn40ToGmPVdcup\nqcZgB94K76MXRnCg1eUp+Lul+t/Y279CEvjnWliL7+fePCrQWOLcDqZVoJjqlF9J\nMmgjZIXNStB2Kxypf+C/jxXKp8LYiV5SY1+CAsoYCwct+5/h9v7beisCvBCTmCpr\n7QIDAQAB\n-----END PUBLIC KEY-----\n'
    public_key=b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoAdYduVrNRPyQOsH/sJL\nDyGPh/D1NjhTvZ0kPX2qg034BFVwmTRXf16QzVWupXV0ROX6OCMdSvQ/49UQlQoc\nglPHjstuSKRPOy1cpp2r3hXBPNMAm6dHFw1cXuywdbp7q8e4YWnt87IAtR/QCfvt\nlbCKBi4Lvzwoz/2/80gg4mnPGH7Eg1eg3s4b2fJ+Bpk63VVq+TAvWTBbNB+x/ApX\nb8e1/SWZYQNhZ+CuBY0VF3Daa/GHGHmSLScUVr/8sOMKLGUtnpjWxp5zDlpXBauV\nQtAyafUA1gWL+ZdB35wdAqR4T37BMUamE5CBYbDKFyI+qhjeZCC2+AbTKnBx7G17\nIQIDAQAB\n-----END PUBLIC KEY-----\n'