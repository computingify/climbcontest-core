#!/bin/bash
# =============================================================================
# Pose le socle ClimbContest sur une VM neuve. Idempotent : relançable.
#
#   scp -r deployment adrien@192.168.0.32:/tmp/
#   ssh adrien@192.168.0.32 'sudo bash /tmp/deployment/install.sh'
#
# Ce script ne deploie AUCUN code applicatif : il prepare la machine pour que
# l'agent de tirage (climbcontest-deploy) puisse le faire. Separation voulue —
# l'installation est rare, le deploiement est frequent.
# =============================================================================
set -euo pipefail

UTILISATEUR="climbcontest"
BASE="/opt/climbcontest"
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "a lancer en root (sudo)"; exit 1; }

echo "== paquets =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl jq sqlite3 >/dev/null

echo "== compte de service =="
if ! id "$UTILISATEUR" >/dev/null 2>&1; then
  useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin "$UTILISATEUR"
  echo "   utilisateur $UTILISATEUR cree"
else
  echo "   utilisateur $UTILISATEUR deja present"
fi

echo "== arborescence =="
# shared/ survit aux deploiements : la base et les secrets ne sont JAMAIS dans
# une release. C'est ce qui permet de deployer et de revenir en arriere sans
# jamais toucher aux donnees.
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0755 "$BASE" "$BASE/releases" "$BASE/shared"
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0750 "$BASE/shared/sauvegardes"
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0750 "$BASE/shared/data"
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0700 "$BASE/shared/secrets"

if [ ! -f "$BASE/shared/secrets/env" ]; then
  cat > "$BASE/shared/secrets/env" <<'EOF'
# Secrets et reglages du service. Charge par systemd (EnvironmentFile).
# Ce fichier n'est JAMAIS versionne. A remplir avec la spec 002.
#
# CLIMBCONTEST_API_KEY=
# CLIMBCONTEST_SECRET_KEY=
# CLIMBCONTEST_SPREADSHEET_ID=
EOF
  chown "$UTILISATEUR:$UTILISATEUR" "$BASE/shared/secrets/env"
  chmod 0600 "$BASE/shared/secrets/env"
  echo "   gabarit shared/secrets/env cree"
fi

echo "== droit de redemarrage cible =="
# L'agent de tirage tourne en tant que climbcontest et doit pouvoir redemarrer
# LE SEUL service climbcontest. Rien d'autre : pas de sudo general.
#
# La quatrieme ligne est le bouton de la console (spec 031) : l'application
# demarre l'agent de deploiement, elle ne l'execute pas elle-meme. Les arguments
# sont listes en entier -- sudo compare la ligne de commande complete, donc
# cette autorisation ne permet PAS de demarrer un autre service.
cat > /etc/sudoers.d/climbcontest <<EOF
$UTILISATEUR ALL=(root) NOPASSWD: /bin/systemctl restart climbcontest, /bin/systemctl stop climbcontest, /bin/systemctl start climbcontest, /bin/systemctl start --no-block climbcontest-deploy.service
EOF
chmod 0440 /etc/sudoers.d/climbcontest
visudo -cf /etc/sudoers.d/climbcontest >/dev/null || { echo "sudoers invalide"; rm -f /etc/sudoers.d/climbcontest; exit 1; }

echo "== scripts =="
install -o root -g root -m 0755 "$ICI/climbcontest-deploy"   /usr/local/bin/
install -o root -g root -m 0755 "$ICI/climbcontest-rollback" /usr/local/bin/
install -o root -g root -m 0755 "$ICI/climbcontest-sauvegarde" /usr/local/bin/

echo "== unites systemd =="
install -m 0644 "$ICI/climbcontest.service"        /etc/systemd/system/
install -m 0644 "$ICI/climbcontest-deploy.service" /etc/systemd/system/
install -m 0644 "$ICI/climbcontest-sauvegarde.service" /etc/systemd/system/
install -m 0644 "$ICI/climbcontest-sauvegarde.timer"   /etc/systemd/system/
systemctl daemon-reload

# Le service applicatif est active mais PAS demarre : il n'y a pas encore de
# release. climbcontest-deploy.service est un oneshot SANS minuteur : il est
# declenche a la demande, depuis la console ou a la main (spec 031). Le tirage
# automatique toutes les 2 min a ete retire le 2026-09-03 -- il consommait la
# moitie du quota GitHub anonyme (60 requetes/h par adresse IP publique) et
# deployait sans que personne ne l'ait demande.
systemctl enable climbcontest.service >/dev/null
systemctl enable --now climbcontest-sauvegarde.timer >/dev/null

echo
echo "Socle en place."
echo "  Premier deploiement :  sudo systemctl start climbcontest-deploy.service"
echo "  Suivre :  journalctl -t climbcontest-deploy -f"
echo "  Etat   :  systemctl status climbcontest"
