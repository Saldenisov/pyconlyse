import requests
from json import dumps

#j_string = {"Outputs": [{"ID": 3,  "Action": 1}, {"ID": 2,  "Action": 0}]}
j_string = {"Outputs": []}

#r = requests.post('http://10.20.30.40/netio.json', json=j_string, auth=('radiolyse', 'Elys3!lcp'))
r = requests.get('http://10.20.30.43/netio.json', auth=('radiolyse', 'Elys3!lcp'))
print(type(r))
print('STATUS: ', r.status_code)

print(r.json())