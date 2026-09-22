from flask import Blueprint, render_template
from models.db import Session
from test_api import test_open_meteo

bp_meteo_paris = Blueprint("meteo_paris", __name__)

@bp_meteo_paris.route("/meteo_paris")
def afficher():
    session = Session()

    try:
        meteo = test_open_meteo()

        return render_template(
            "meteo_paris.html",
            meteo=meteo
        )

    finally:
        session.close()