"""Read-only XP TCP capacity evidence. No NI, service restart or registry writes."""
import ctypes
import datetime
import json
import os
import socket
import struct
import sys
import time
import traceback
import winreg

BASE = os.path.dirname(os.path.abspath(__file__))

def snapshot():
    DWORD = ctypes.c_uint32
    api = ctypes.windll.iphlpapi.GetTcpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(DWORD), ctypes.c_int]
    api.restype = DWORD
    size = DWORD(0)
    result = api(None, ctypes.byref(size), 0)
    if result not in (0, 122) or not 4 <= size.value <= 16*1024*1024:
        raise ValueError('Unexpected bounded TCP table size')
    for unused in range(3):
        buffer = ctypes.create_string_buffer(size.value)
        result = api(buffer, ctypes.byref(size), 0)
        if result == 122:
            continue
        if result:
            raise OSError('GetTcpTable result ' + str(result))
        break
    else:
        raise ValueError('TCP table changed during bounded retries')
    raw = buffer.raw
    count = struct.unpack_from('<I', raw)[0]
    if 4+count*20 > len(raw):
        raise ValueError('TCP table row bound differs')
    states, camera, relay = {}, {}, {}
    camera_ports, outbound_ports = set(), set()
    for index in range(count):
        state, local, lp, remote, rp = struct.unpack_from('<IIIII', raw,4+index*20)
        lp, rp = socket.ntohs(lp & 0xffff), socket.ntohs(rp & 0xffff)
        local_ip, remote_ip = socket.inet_ntoa(struct.pack('<I',local)), socket.inet_ntoa(struct.pack('<I',remote))
        states[str(state)] = states.get(str(state),0)+1
        if 1024 < lp <= 5000:
            outbound_ports.add(lp)
        if remote_ip == '127.0.0.1' and rp == 8768:
            camera[str(state)] = camera.get(str(state),0)+1
            camera_ports.add(lp)
        if remote_ip == '10.20.30.202' and rp == 8767:
            relay[str(state)] = relay.get(str(state),0)+1
    parameters = {}
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters',0,winreg.KEY_READ) as key:
        for name in ('MaxUserPort','TcpTimedWaitDelay'):
            try:
                parameters[name] = winreg.QueryValueEx(key,name)[0]
            except FileNotFoundError:
                parameters[name] = None
    return dict(utc=datetime.datetime.utcnow().isoformat()+'Z', total_rows=count,
        state_counts=states,camera_client_states=camera,everest_relay_client_states=relay,
        camera_client_unique_local_ports=len(camera_ports),
        camera_client_port_range=[min(camera_ports),max(camera_ports)] if camera_ports else None,
        occupied_local_ports_1025_to_5000=len(outbound_ports),registry_explicit_values=parameters,
        state11_means='TIME_WAIT',registry_writes=False,hardware_commands_sent=False)

try:
    if os.name!='nt' or sys.version_info[:2]!=(3,4):
        raise ValueError('XP Python3.4 required')
    if '10.20.30.2' not in socket.gethostbyname_ex(socket.gethostname())[2]:
        raise ValueError('SuperVision host required')
    rows=[]
    for index in range(3):
        rows.append(snapshot())
        if index<2:
            time.sleep(1)
    report=dict(state='READ_ONLY_TCP_EVIDENCE',rows=rows)
except BaseException:
    report=dict(state='FAILED',error=traceback.format_exc())
with open(os.path.join(BASE,'xp_tcp_evidence.json'),'w',encoding='utf-8') as stream:
    json.dump(report,stream,indent=2)
