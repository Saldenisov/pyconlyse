import requests

addr_on = 'http://10.20.30.47/?status=ON'
addr_off = 'http://10.20.30.47/?status=OFF'


requests.get(url=addr_off)