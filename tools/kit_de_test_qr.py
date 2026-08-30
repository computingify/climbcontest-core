"""Les QR de la compétition ACTIVE, sur une page à imprimer ou à afficher.

Pour répéter le jour J : de vrais QR à scanner avec de vrais téléphones, sans
imprimer les dossards d'une vraie compétition.

    python3 tools/kit_de_test_qr.py > kit.html

Lit la base, n'écrit rien. Les QR sont générés localement (`climbcontest.qr`),
comme ceux des dossards — même contenu, donc même comportement au scan.
"""
import sys

from climbcontest import creer_app, qr
from climbcontest.models import Bloc, Competition, Participant

HEX = {"jaune": "#F5B72E", "vert": "#34C56A", "bleu": "#3E8CF7",
       "mauve": "#A86CF0", "violet": "#A86CF0", "rouge": "#F0554A",
       "noir": "#E8EBF0"}


def carte(titre, sous, code, couleur=None):
    teinte = HEX.get((couleur or "").strip().lower(), "#3E4B5E")
    return (f'<div class="carte" style="border-top:10px solid {teinte}">'
            f'{qr.svg(code, cote_mm=38)}'
            f'<div class="t">{titre}</div><div class="s">{sous}</div></div>')


def page(comp, participants, blocs):
    grimpeurs = "".join(
        carte(f"Dossard {p.dossard}", f"{p.prenom or ''} {p.nom} · {p.categorie or ''}".strip(),
              str(p.dossard))
        for p in participants if p.dossard is not None)
    murs = "".join(
        carte(b.tag, f"Bloc {b.numero} · circuit {b.couleur or '?'}", b.tag, b.couleur)
        for b in blocs)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Kit de test — {comp.nom}</title>
<style>
 body{{font-family:system-ui,-apple-system,sans-serif;margin:24px;color:#191C22}}
 h1{{font-size:1.4rem}} h2{{font-size:1rem;margin:28px 0 10px;text-transform:uppercase;
    letter-spacing:.1em;color:#545C6B}}
 p{{max-width:70ch;color:#545C6B}}
 .grille{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}}
 .carte{{border:1px solid #D6DAE3;border-radius:10px;padding:10px;text-align:center;
   background:#fff;break-inside:avoid}}
 .carte svg{{width:100%;height:auto;max-width:130px}}
 .t{{font-weight:700;margin-top:6px}} .s{{font-size:.8rem;color:#545C6B}}
 @media print{{ .grille{{grid-template-columns:repeat(4,1fr)}} }}
</style></head><body>
<h1>Kit de test ClimbContest — « {comp.nom} »</h1>
<p>Les QR de la compétition active. Ils se scannent <strong>imprimés</strong> comme
<strong>affichés sur un écran</strong>. Le geste : un dossard, puis un bloc, puis
ENVOYER — et le résultat apparaît sur la page de résultats, dans la console
(onglet Appareils) et dans le classeur relié.</p>
<h2>Grimpeurs — le QR encode le dossard</h2><div class="grille">{grimpeurs}</div>
<h2>Blocs — le QR encode le tag</h2><div class="grille">{murs}</div>
</body></html>"""


if __name__ == "__main__":
    app = creer_app()
    with app.app_context():
        comp = Competition.query.filter_by(active=True).first()
        if comp is None:
            sys.exit("Aucune competition active.")
        participants = (Participant.query.filter_by(competition_id=comp.id)
                        .order_by(Participant.dossard).all())
        blocs = (Bloc.query.filter_by(competition_id=comp.id)
                 .order_by(Bloc.numero).all())
        sys.stdout.write(page(comp, participants, blocs))
