import msgpack
import zlib
import numpy as np
data = {1258461125: np.zeros(shape=(1024, 10)).tobytes()}
a_m = msgpack.packb(data)
a_z = zlib.compress(a_m)
a_s = str(a_z)
b_z = eval(a_s)
b_z = zlib.decompress(b_z)
b = msgpack.unpackb(b_z, strict_map_key=False)

print(b.keys())