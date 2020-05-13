import hashlib
import os

salt = os.urandom(32) # Remember this
password = 'password123'

key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt,  100000)


a = 0