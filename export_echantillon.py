import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

# Échantillon : Reims, 7 jours, un seul modèle.
# Format de sortie : partie A du contrat d'interface v1.1 (22/11/2026).
CODE_INSEE = "51454"        # texte sur 5 caractères, jamais un nombre
MODELE = "MRI_AGCM3_2_S"    # le modèle n'est pas dans la série (voir le nom du fichier)

parametres = {
    "latitude": 49.2583,
    "longitude": 4.0317,
    "start_date": "2049-04-01",
    "end_date": "2049-04-07",
    "models": MODELE,
    "daily": (
        "temperature_2m_min,temperature_2m_max,"
        "temperature_2m_mean,precipitation_sum"
    ),
}

url = "https://climate-api.open-meteo.com/v1/climate?"
url += urlencode(parametres)

try:
    with urlopen(url, timeout=20) as reponse:
        donnees = json.load(reponse)
except HTTPError as erreur:
    detail = erreur.read().decode("utf-8", errors="replace")
    raise SystemExit(f"Open-Meteo a refusé la requête (HTTP {erreur.code}) : {detail}")
except (URLError, TimeoutError) as erreur:
    raise SystemExit(f"Open-Meteo est injoignable : {erreur}")
except json.JSONDecodeError:
    raise SystemExit("La réponse d'Open-Meteo n'est pas du JSON valide.")

if "daily" not in donnees:
    raise ValueError("Réponse sans bloc 'daily' : " + str(donnees)[:200])

jours = donnees["daily"]

# Correspondance contrat -> nom Open-Meteo (partie A du contrat).
champs = {
    "t_min": "temperature_2m_min",
    "t_max": "temperature_2m_max",
    "t_moy": "temperature_2m_mean",
    "precip": "precipitation_sum",
}
COLONNES_CONTRAT = ["code_insee", "date", "t_min", "t_max", "t_moy", "precip"]

dates = jours["time"]
if not dates or len(set(dates)) != len(dates):
    raise ValueError("Dates absentes ou en double.")

for champ_api in champs.values():
    if len(jours[champ_api]) != len(dates):
        raise ValueError("Tableaux de tailles différentes.")

serie = []
for i, date in enumerate(dates):
    ligne = {"code_insee": CODE_INSEE, "date": date}
    for champ_contrat, champ_api in champs.items():
        ligne[champ_contrat] = jours[champ_api][i]  # null reste None, jamais 0
    serie.append(ligne)

# Contrôles du contrat avant d'écrire le fichier.
for ligne in serie:
    if list(ligne.keys()) != COLONNES_CONTRAT:
        raise ValueError(f"Colonnes différentes du contrat : {list(ligne.keys())}")
    if ligne["precip"] is not None and ligne["precip"] < 0:
        raise ValueError(f"Précipitation négative le {ligne['date']} (interdit par le contrat).")

nom_fichier = f"serie_{CODE_INSEE}_{MODELE}.json"
with open(nom_fichier, "w", encoding="utf-8") as fichier:
    json.dump(serie, fichier, ensure_ascii=False, indent=2,
              allow_nan=False)

print(f"Export terminé : {len(serie)} journées dans {nom_fichier}.")
