# point d'entrée
import os
from flask import Flask
from config import Config

from controllers.accueil import bp_accueil
from controllers.meteo_paris import bp_meteo_paris

app = Flask(__name__)
app.config.from_object(Config)

class _PrefixMiddleware:
    """Sert l'application sous un sous-chemin (ex: /sae201_b1) en production.
    Alwaysdata transmet le sous-chemin dans l'URL sans le retirer : on le déplace
    de PATH_INFO vers SCRIPT_NAME pour que le routage et url_for restent corrects.
    Inactif en local (APP_BASE_URL non défini)."""

    def __init__(self, wsgi_app, prefix):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
        return self.wsgi_app(environ, start_response)

# Préfixe d'URL pour un futur déploiement en sous-dossier (vide en local).
app.config["BASE_URL"] = os.getenv("APP_BASE_URL", "")

_prefix = os.getenv("APP_BASE_URL", "").rstrip("/")
if _prefix:
    app.wsgi_app = _PrefixMiddleware(app.wsgi_app, _prefix)

_prefix = os.getenv("APP_BASE_URL", "").rstrip("/")
if _prefix:
    app.wsgi_app = _PrefixMiddleware(app.wsgi_app, _prefix)

# Enregistrement des contrôleurs (blueprints)
app.register_blueprint(bp_accueil)
app.register_blueprint(bp_meteo_paris)

@app.context_processor
def inject_base_url():
    """Rend BASE_URL disponible dans tous les templates."""
    return {"BASE_URL": app.config["BASE_URL"]}

if __name__ == "__main__":
    app.run(debug=True)