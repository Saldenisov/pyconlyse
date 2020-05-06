from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

MESSAGE = b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArp8Sl+X9tgrXxGuTk+IJ\naSTsLFwLmY4rCz96i6ziuA1fd1DjaN2aUeXScosTjn6kNrQCb+fFStA941+k7AdB\n1QKsUJX6/zdvIzDwLwt7fFulXgWgtLFeqiQNo4jg9pdi7zIB1ztQVGbqxArINMY0\nrsEYd0fWIec9zWliUW+cmGB8xjjPu/LtoDt8ZuQLBh9DuGNUdBzn40ToGmPVdcup\nqcZgB94K76MXRnCg1eUp+Lul+t/Y279CEvjnWliL7+fePCrQWOLcDqZVoJjqlF9J\nMmgjZIXNStB2Kxypf+C/jxXKp8LYiV5SY1+CAsoYCwct+5/h9v7beisCvBCTmCpr\n7QIDAQAB\n-----END PUBLIC KEY-----\n'
pub_key_bytes = b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoAdYduVrNRPyQOsH/sJL\nDyGPh/D1NjhTvZ0kPX2qg034BFVwmTRXf16QzVWupXV0ROX6OCMdSvQ/49UQlQoc\nglPHjstuSKRPOy1cpp2r3hXBPNMAm6dHFw1cXuywdbp7q8e4YWnt87IAtR/QCfvt\nlbCKBi4Lvzwoz/2/80gg4mnPGH7Eg1eg3s4b2fJ+Bpk63VVq+TAvWTBbNB+x/ApX\nb8e1/SWZYQNhZ+CuBY0VF3Daa/GHGHmSLScUVr/8sOMKLGUtnpjWxp5zDlpXBauV\nQtAyafUA1gWL+ZdB35wdAqR4T37BMUamE5CBYbDKFyI+qhjeZCC2+AbTKnBx7G17\nIQIDAQAB\n-----END PUBLIC KEY-----\n'


public_key = load_pem_public_key(pub_key_bytes, backend=default_backend())

try:
    # Encrypt
    ciphertext = public_key.encrypt(
        MESSAGE,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None
        )
    )
except Exception as e:
    print(e)

