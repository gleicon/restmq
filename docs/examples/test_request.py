import requests

payload = {'value': 'el requesto',}
r = requests.post("http://localhost:8888/q/test", data=payload)
print r.text
