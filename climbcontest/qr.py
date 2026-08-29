"""QR code des dossards, genere localement.

POURQUOI PAS UN SERVICE
  Le classeur genere ses QR avec `api.qrserver.com`. Deux consequences : les
  dossards -- donc les personnes qu'ils designent -- partent chez un tiers, et
  imprimer les dossards le matin de la competition demande une connexion
  Internet qui fonctionne. Les deux sont evitables.

POURQUOI PAS UN ENCODEUR MAISON
  J'en ai ecrit un. Il produisait des matrices d'allure correcte que AUCUN
  decodeur ne lisait -- 0 sur 9 avec OpenCV, sur un harnais dont j'ai ensuite
  verifie qu'il lit parfaitement des QR valides de meme taille. C'est le genre
  de defaut qui se decouvre le jour J, sur un parking, avec 120 dossards deja
  imprimes.

  Mon estimation (« ~150 lignes pour du numerique ») sous-estimait le placement
  de l'information de format et le masquage. Et la premisse etait fausse aussi :
  je voulais eviter une dependance qui tire Pillow, or `segno` n'en tire aucune.
  Python pur, sans extension native.

⚠️ LE PIEGE QUI A COUTE LE PLUS DE TEMPS
  `segno.make()` choisit tout seul un MICRO QR pour des donnees courtes -- une
  symbologie differente, 13x13, que la plupart des scanners de telephone ne
  lisent pas. Un dossard fait un a quatre chiffres : on tombe dedans a tous les
  coups.

  D'ou `make_qr()`, qui force un QR standard. Un test verifie explicitement que
  ce n'est pas un Micro QR -- c'est exactement le genre de regression qui
  passerait toutes les autres verifications.
"""
import io

import segno

# Correction M (~15 %). Largement suffisant pour un papier tenu a vingt
# centimetres d'un telephone -- et plus dense qu'un niveau superieur, donc des
# modules plus GROS a taille de papier egale, donc plus lisible.
CORRECTION = "m"


def code(texte: str):
    """Le QR standard d'un dossard. Jamais un Micro QR."""
    return segno.make_qr(str(texte).strip(), error=CORRECTION)


def svg(texte: str, cote_mm: float = 22.0) -> str:
    """Le QR en SVG, dimensionne en millimetres pour l'impression.

    La taille est donnee en mm et non en pixels : ce qui compte est la taille
    PHYSIQUE sur le papier, pas le nombre de modules -- lequel change selon le
    nombre de chiffres du dossard.
    """
    # segno ecrit des OCTETS, meme en SVG : un StringIO leve une TypeError.
    tampon = io.BytesIO()
    code(texte).save(tampon, kind="svg", scale=1, border=2,
                     xmldecl=False, svgversion=None, omitsize=True)
    return tampon.getvalue().decode("utf-8").replace(
        "<svg ", f'<svg width="{cote_mm}mm" height="{cote_mm}mm" ', 1)


def matrice(texte: str) -> list[list[int]]:
    """La matrice de modules, 1 = noir. Pour les tests."""
    return [[1 if module else 0 for module in ligne] for ligne in code(texte).matrix]
