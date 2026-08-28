"""Point d'entree gunicorn de ClimbContest.

    gunicorn wsgi:app

La fabrique vit dans climbcontest/__init__.py. Ce fichier ne fait que
l'appeler : deployment/climbcontest.service n'a jamais besoin de changer.
"""
from climbcontest import creer_app

app = creer_app()
