from flask import Blueprint, render_template
from models.db import Session

bp_accueil = Blueprint("accueil", __name__)
@bp_accueil.route("/")

def index():
    session = Session()
    try:
        return render_template("accueil.html")
    finally:
        session.close()

# <!DOCTYPE html>
#     <html lang="fr">
#         <head>
#             <meta charset="UTF-8">
#             <title>Test</title>
#         </head>
#         <body>
#             <h1>Hello World!</h1>
#         </body>
#     </html>