
import requests
import json

def test_query():
    url = "http://localhost:8000/api/v1/query"
    payload = {
        "query": "forecast demand for next month",
        "agent_type": "demand"
    }
    
    print(f"Sending POST to {url} with payload: {payload}")
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_query()
