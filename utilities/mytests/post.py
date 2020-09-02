import requests
from json import dumps

j_string = {"Outputs": [{"ID": 4,  "Action": 0}, {"ID": 2,  "Action": 0
                                                   }]}

r = requests.post('http://10.20.30.43/netio.json', json=j_string, auth=('radiolyse', 'Elys3!lcp'))
#r = requests.get('http://10.20.30.43/netio.json', auth=('radiolyse', 'Elys3!lcp'))

print('STATUS: ', r.status_code)

print(r.json())