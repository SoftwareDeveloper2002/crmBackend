import requests

url = "http://3.27.40.236/sms/send"

payload = {
    "api_key": "taena",
    "number": "09065795804",
    "message": "Hello World Ngani!"
}

try:
    response = requests.post(url, json=payload, timeout=10)

    if response.status_code == 200:
        print("SMS Sent Successfully!")
        print("Response:", response.json())
    else:
        print(f"Failed to send SMS. Status: {response.status_code}")
        print("Response:", response.text)

except requests.exceptions.RequestException as e:
    print("Error:", e)
