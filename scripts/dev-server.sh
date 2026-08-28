#!/bin/bash
# =============================================================================
# Backend de developpement, pour tester l'application juge dans l'emulateur.
#
#   ./scripts/dev-server.sh              demarre, base peuplee
#   ./scripts/dev-server.sh --neuf       repart d'une base vide
#   ./scripts/dev-server.sh --port 5008  autre port
#   ./scripts/dev-server.sh --reseau     accessible depuis un telephone du wifi
#
# L'emulateur Android voit la machine hote a l'adresse 10.0.2.2, qui pointe sur
# la boucle locale de l'hote : l'ecoute sur 127.0.0.1 lui suffit. L'application
# compilee en debug pointe sur http://10.0.2.2:5007 sans rien a configurer.
#
# Un telephone PHYSIQUE, lui, passe par le wifi et a besoin de --reseau. Ce
# n'est pas le defaut : ce backend sert un jeu de donnees complet sans
# authentification, et l'ouvrir a tout le reseau -- un wifi de salle, un cafe --
# n'a pas a arriver par accident.
#
# Le jeu de donnees reprend la structure de la vraie competition de novembre
# 2025 -- 8 categories, 4 circuits, des blocs par zone -- avec des noms
# fictifs. Assez realiste pour que les ecrans de l'application ressemblent a ce
# qu'ils afficheront le jour J.
# =============================================================================
set -uo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

PORT=5007
NEUF=0
ADRESSE=127.0.0.1
while [ $# -gt 0 ]; do
  case "$1" in
    --neuf)  NEUF=1; shift ;;
    --port)  PORT="$2"; shift 2 ;;
    --reseau) ADRESSE=0.0.0.0; shift ;;
    -h|--help) sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "option inconnue : $1"; exit 1 ;;
  esac
done

DONNEES="$RACINE/instance/dev"
export CLIMBCONTEST_DATA_DIR="$DONNEES"
export CLIMBCONTEST_SHEETS_ACTIF=0        # aucun acces au classeur en dev
export CLIMBCONTEST_API_KEY="dev"
export CLIMBCONTEST_API_KEY_STRICTE=0     # comme en production aujourd'hui

VENV="$RACINE/.venv-dev"
if [ ! -x "$VENV/bin/python" ]; then
  echo "== environnement Python =="
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  # requirements-dev.txt, pas requirements.txt : cet environnement sert aussi a
  # lancer pytest. Avec le seul fichier de production, `pytest` etait absent et
  # la suite ne pouvait pas tourner ici.
  "$VENV/bin/pip" install --quiet -r requirements-dev.txt
fi

if [ "$NEUF" = 1 ]; then
  echo "== base remise a zero =="
  rm -rf "$DONNEES"
fi
mkdir -p "$DONNEES"

echo "== jeu de donnees =="
"$VENV/bin/python" scripts/seed_dev.py || exit 1

cat <<EOF

  Backend de developpement pret.

  Depuis l'emulateur Android : http://10.0.2.2:$PORT
  Depuis ce Mac              : http://127.0.0.1:$PORT
$(if [ "$ADRESSE" = 0.0.0.0 ]; then
    IP=$(ipconfig getifaddr en0 2>/dev/null || echo "<ip-de-ce-mac>")
    echo "  Depuis un telephone du wifi: http://$IP:$PORT"
    echo "  /!\\ ouvert a tout le reseau local, jeu de donnees sans authentification"
  fi)
  Installer l'application    : cd ../climbcontest-android && ./gradlew installDebug
  Suivre les requetes        : elles s'affichent ci-dessous
  Arreter                    : Ctrl+C

EOF

exec "$VENV/bin/gunicorn" --workers 2 --threads 4 --worker-class gthread \
     --bind "$ADRESSE:$PORT" --access-logfile - --error-logfile - \
     --log-level info wsgi:app
