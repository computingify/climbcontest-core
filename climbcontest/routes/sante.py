"""Sonde de sante et page d'accueil provisoire."""
import os
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from ..version import VERSION

bp = Blueprint("sante", __name__)

# ⚠️ `VERSION` etait lu ICI, par une fonction privee de ce module. La spec 030 a
# eu besoin du meme numero dans la console et dans la route du catalogue : il
# est passe dans `climbcontest/version.py`, importe ci-dessus. La sonde ne
# change pas d'un iota -- elle repond toujours la meme chose -- mais deux autres
# appelants peuvent enfin le lire sans importer une route.


@bp.get("/health")
def health():
    """Sonde. Ne depend d'aucun service EXTERNE -- mais bien de la base.

    Volontairement sans acces au classeur Google : une sonde qui tombe parce
    qu'un tiers est lent declencherait des retours arriere de deploiement et des
    alertes pour rien.

    La base, elle, n'est pas un tiers : c'est le service. Une sonde qui repond
    « ok » sans l'avoir interrogee ne mesure rien. Elle a d'ailleurs deja laisse
    passer le pire cas -- quatre workers demarres sur une base sans tables :
    l'exception etait avalee ici, `reussites_en_attente` valait `null`, le
    statut restait « ok », et l'agent de deploiement validait la mise en
    production d'un serveur ou chaque scan renvoyait 500.

    Desormais : si la base n'est pas interrogeable, la sonde repond **503
    degraded**. C'est ce qui doit declencher le retour arriere, pas ce qu'il
    faut cacher pour l'eviter.

    Meme raisonnement pour la cle d'API (spec 012). En mode strict sans aucune
    cle configuree, TOUTES les routes du juge repondent 503 : le service tourne,
    mais il est inutilisable. Sans cette verification, l'agent de deploiement
    verrait « ok », validerait la mise en production, et la panne se
    decouvrirait quand vingt-cinq juges commenceraient a scanner.

    `reussites_en_attente` dit si le miroir vers le classeur suit. Un nombre qui
    monte sans redescendre = le classeur n'est plus alimente, mais AUCUNE donnee
    n'est perdue : tout est en base.
    """
    corps = {"status": "ok", "version": VERSION}
    code = 200
    try:
        from ..contest import reussites_en_attente, reussites_inenvoyables
        from ..sans_classeur import actif as sans_classeur_actif

        # ⚠️ LE MODE SE NOMME, ET LE STATUT RESTE « ok » (spec 046).
        #
        # Les deux compteurs a `null` signifient, deux lignes plus bas, « base
        # injoignable » -- et cette sonde-la fait repondre 503 degraded, ce qui
        # declenche le retour arriere automatique de l'agent de deploiement.
        # Les poser a `null` sans dire pourquoi ferait donc DESINSTALLER la
        # version au premier deploiement suivant la bascule, et la sonde
        # aurait l'air de marcher.
        #
        # Le mode sans classeur n'est pas une panne : il n'y a plus de miroir,
        # donc plus rien a compter.
        corps["mode_sans_classeur"] = sans_classeur_actif()
        if corps["mode_sans_classeur"]:
            corps["reussites_en_attente"] = None
            corps["reussites_inenvoyables"] = None
        else:
            corps["reussites_en_attente"] = reussites_en_attente()
            # Le retard qui se rattrape d'un côté, ce qui n'ira jamais de
            # l'autre. Les mélanger rendait le premier illisible.
            corps["reussites_inenvoyables"] = reussites_inenvoyables()
    except Exception as e:
        corps["reussites_en_attente"] = None
        corps["reussites_inenvoyables"] = None
        corps["status"] = "degraded"
        corps["base"] = f"injoignable : {type(e).__name__}"
        code = 503

    # Une configuration qui rend le service inutilisable doit se voir ici, et
    # faire echouer le deploiement.
    from ..auth import cles_acceptees
    if current_app.config.get("API_KEY_STRICTE") and not cles_acceptees():
        corps["status"] = "degraded"
        corps["cle_api"] = ("aucune cle configuree alors que le mode strict est "
                            "actif : poser CLIMBCONTEST_API_KEY, ou "
                            "CLIMBCONTEST_API_KEY_STRICTE=0")
        code = 503

    # ⚠️ Compteurs PAR WORKER, pas globaux. Avec 4 workers gunicorn, ce que
    # vous lisez ici est la vue d'un seul d'entre eux. Pour savoir si quelqu'un
    # appelle encore sans cle d'API -- la question qui decide du passage en mode
    # strict -- utiliser le journal, qui agrege tout :
    #   journalctl -u climbcontest --since today | grep -c "appel sans cle"
    from ..auth import compteurs
    from ..sheets.planificateur import est_actif
    # Le REGIME et le NOMBRE de cles, jamais les cles -- ni meme un prefixe :
    # un prefixe reduit l'espace de recherche sans rien apprendre a qui a acces
    # a la configuration de la VM.
    corps["api"] = {
        **compteurs,
        "regime": "strict" if current_app.config.get("API_KEY_STRICTE") else "tolere",
        "cles_acceptees": len(cles_acceptees()),
        "portee": "ce worker seulement",
        "pid": os.getpid(),
    }
    corps["miroir_actif"] = est_actif()
    # La derniere plainte du miroir, pour diagnostiquer sans SSH. `null` quand
    # tout va bien -- ou que le fil n'a pas encore essaye.
    from ..sheets.planificateur import derniere_erreur
    corps["miroir_derniere_erreur"] = derniere_erreur()
    # Meme raisonnement pour HelloAsso : le 30/08 il a fallu ouvrir un SSH
    # pour apprendre pourquoi 714 reussites attendaient, alors que la cause
    # etait deja dans une variable locale. On ne recommence pas.
    from ..helloasso.planificateur import (
        derniere_erreur as helloasso_erreur, dernier_releve)
    corps["helloasso_derniere_erreur"] = helloasso_erreur()
    corps["helloasso_dernier_releve"] = dernier_releve()
    corps["sauvegarde"] = _etat_sauvegarde()
    return jsonify(corps), code


def _etat_sauvegarde() -> dict:
    """Age de la derniere recopie locale de la base.

    Exposee ici pour une raison precise : le 29/08, le miroir vers le classeur
    Google etait casse en silence depuis des heures. Une sauvegarde qui
    s'arrete doit SE VOIR -- sinon on ne le decouvre que le jour ou on en a
    besoin, c'est-a-dire au pire moment.

    Ne fait jamais echouer la sonde : ne pas savoir sauvegarder n'est pas la
    meme chose que ne pas savoir servir.
    """

    try:
        dossier = Path(current_app.config["DOSSIER_SAUVEGARDES"])
        copies = sorted(dossier.glob("climbcontest-*.db"))
        if not copies:
            return {"copies": 0, "derniere_il_y_a_s": None}
        derniere = max(copies, key=lambda f: f.stat().st_mtime)
        return {
            "copies": len(copies),
            "derniere_il_y_a_s": round(time.time() - derniere.stat().st_mtime),
            "derniere_octets": derniere.stat().st_size,
        }
    except Exception as e:
        return {"copies": None, "erreur": type(e).__name__}


# La racine servait un JSON de service, avec pour tout message « la page de
# resultats arrive avec la spec 006 ». Elle est arrivee : c'est desormais
# routes/pages.py qui repond sur « / ». Un visiteur qui tape l'adresse du
# service doit voir le classement, pas un objet JSON.
