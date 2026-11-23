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

    # Afficher les 5 premières valeurs
    print("Exemple de données:", data["hourly"]["temperature_2m"][:5])

if __name__ == "__main__":
    test_open_meteo()