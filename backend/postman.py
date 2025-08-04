import requests

url = "http://localhost:8000/api/predict-campaigns/custom-date/"
data = {
    "from_date": "2025-07-01",
    "to_date": "2025-07-30",
    "timezone": "Europe/Amsterdam"
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=data, headers=headers)
print(response.json())
