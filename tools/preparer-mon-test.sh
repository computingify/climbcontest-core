#!/usr/bin/env bash
# Les deux derniers gestes avant de pouvoir tester — ils demandent TON mot de
# passe, c'est pourquoi ils ne sont pas automatisés.
#
#   bash preparer-mon-test.sh
#
# Tout le reste est déjà fait sur la VM : clé PWA posée, compétition de test
# « Test septembre 2026 » active (8 grimpeurs, 24 blocs, classeur jetable relié).
set -euo pipefail

VM=adrien@192.168.0.32
CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "──────────────────────────────────────────────────────────"
echo " 1/2  Le jeton Google — sans lui, le classeur reste vide"
echo "──────────────────────────────────────────────────────────"
JETON="$HOME/Documents/workspace/annonayEscalade/climbcontest-core/token.pickle"
if [ ! -f "$JETON" ]; then
  echo "✗ token.pickle introuvable à $JETON" >&2; exit 1
fi
scp "$JETON" "$VM:/tmp/token.pickle"
ssh -t "$VM" '
  sudo install -m 600 -o climbcontest -g climbcontest /tmp/token.pickle \
       /opt/climbcontest/shared/secrets/token.pickle
  rm -f /tmp/token.pickle
  sudo systemctl restart climbcontest
  echo "✓ jeton en place, service redémarré"
'

echo
echo "──────────────────────────────────────────────────────────"
echo " 2/2  Ton compte de console (mot de passe demandé)"
echo "──────────────────────────────────────────────────────────"
ssh -t "$VM" '
  cd /opt/climbcontest/current
  sudo -u climbcontest env \
    CLIMBCONTEST_DATA_DIR=/opt/climbcontest/shared/data \
    CLIMBCONTEST_SHEETS_ACTIF=0 CLIMBCONTEST_API_KEY=x \
    FLASK_APP=wsgi .venv/bin/flask creer-admin adrien
'

echo
echo "──────────────────────────────────────────────────────────"
echo " Vérification"
echo "──────────────────────────────────────────────────────────"
sleep 5
curl -s https://climbcontest.adn-dev.fr/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('  statut          :', d['status'], '| version', d['version'])
print('  clés acceptées  :', d['api']['cles_acceptees'], '(2 attendu : Android + PWA)')
print('  miroir, erreur  :', d['miroir_derniere_erreur'] or 'aucune ✓')
print('  en attente      :', d['reussites_en_attente'])
"
echo
echo "Puis : https://climbcontest.adn-dev.fr/console → onglet « App juge »"
echo "pour le QR à scanner avec ton iPhone ou ton Android."
