from datastructures.mes_independent.devices_dataclass import Connection

param = {'device_id': 'Server:Main:sfqvtyjsdf23qa23xcv', 'device_name': 'Server_default', 'device_type': 'server', 'device_public_key': b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtsmUZkHlja1P9Ygpbe6/\nPQ3G8qFgGsqjRDWm1e940BCc3KXYek0spCOp6uIdlGYC5oL7RRpCPMMOJqT/54aU\n64JVykIRt4G79P8qS+Uth3//0zrWBVCT47eaxn3Rr+jf7xmYjU6LxMlOtOBFVqaD\nlWNH30T1ntsRNQEhbxqY3ULTdEQV6p/u5CBmCo9jxPwT/XtDTvQjjx7SgTSR3lnS\nFN/MtL+ehF7CwKKzaUuLmM0dbF43KM9wlhNrBW/Na/wmX+IAZE+SqjVpBJ4DHAhQ\nvPsdlDshHNw+I81qR0qG9LgJNGqWiHgZEMf0+CzFz3GU8fQN537hKe/wuUTE47zw\nvQIDAQAB\n-----END PUBLIC KEY-----\n', 'device_public_sockets': {'publisher_socket_server': 'tcp://127.0.0.1:5556', 'frontend_router_socket_server': 'tcp://127.0.0.1:5001', 'backend_router_socket_server': 'tcp://127.0.0.1:5002'}, 'event_id': 'heartbeat:Server:Main:sfqvtyjsdf23qa23xcv', 'event_name': 'heartbeat'}

a = Connection(**param)
print(a)