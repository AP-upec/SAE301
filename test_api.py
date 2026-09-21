import requests

def test_open_meteo():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "hourly": "temperature_2m",
        "timezone": "Europe/Paris"
    }

    response = requests.get(url, params=params)

    print("Status:", response.status_code)
    data = response.json()

    return data