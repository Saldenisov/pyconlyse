from pathlib import Path
import ctypes

app_folder = Path('C:\dev\pyconlyse\\bin\DeviceServers\OWIS')

dll_path = str(app_folder / 'ps90.dll')
print(dll_path)

lib = ctypes.WinDLL(dll_path)

control_unit = ctypes.c_long(1)
ser_num = ctypes.c_char_p(b"")
res = lib.PS90_SimpleConnect(control_unit, ser_num) * -1  # *-1 is according official documentation
print(f'Connection {res}')
# res = lib.PS90_Disconnect(control_unit)
# print(f'Disconnect {res}')


szString = ctypes.c_char_p()
buf = ctypes.create_string_buffer(500)

print(buf.value.decode("utf-8"))
res = lib.PS90_GetSerNumber(1, buf, 25)
# res = lib.PS90_GetConnectInfo(1, buf, 500)

print(buf.value.decode('utf-8'))


