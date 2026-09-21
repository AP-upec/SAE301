from flask import Blueprint, render_template
from models.db import Session
from test_api import test_open_meteo

bp_accueil = Blueprint("accueil", __name__)

@bp_accueil.route("/")
def afficher():
    session = Session()

    try:
        meteo = test_open_meteo()

        return render_template(
            "accueil.html",
            meteo=meteo
        )

    finally:
        session.close()