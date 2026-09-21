from flask import Blueprint, render_template
from models.db import Session
from test_api import test_open_meteo

bp_teste = Blueprint("teste", __name__)

@bp_teste.route("/teste")
def afficher():
    session = Session()

    try:
        meteo = test_open_meteo()

        return render_template(
            "teste.html",
            meteo=meteo
        )

    finally:
        session.close()