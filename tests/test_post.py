import requests
r = requests.post("http://127.0.0.1:8001/ask", json={"question":"hello","thread_id":"default_user"})
print(r.status_code)
print(r.text)
