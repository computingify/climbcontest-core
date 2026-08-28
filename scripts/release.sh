#!/bin/bash
# =============================================================================
# Publie une release ClimbContest.
#
#   ./scripts/release.sh 0.2.0
#
# Ce script ne construit rien : il verifie, tague et pousse. C'est GitHub qui
# construit et publie (.github/workflows/release.yml), et la VM qui tire.
#
# Les verifications sont faites ICI pour qu'un oubli coute 2 secondes sur ton
# poste plutot qu'un aller-retour avec la CI.
# =============================================================================
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "usage: $0 <version>    (ex: 0.2.0, sans le v)"
  echo
  echo "Derniere release : $(git tag -l 'v*' --sort=-v:refname | head -1)"
  exit 1
fi
VERSION="${VERSION#v}"
TAG="v$VERSION"

echo "== 1. format de version =="
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || { echo "ECHEC : '$VERSION' n'est pas du versionnage semantique (X.Y.Z)."; exit 1; }

echo "== 2. l'etiquette est-elle libre ? =="
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "ECHEC : l'etiquette $TAG existe deja."
  echo "  Une release publiee ne se rejoue pas : passe a la version suivante."
  exit 1
fi

echo "== 3. arbre de travail propre ? =="
if [ -n "$(git status --porcelain)" ]; then
  echo "ECHEC : des modifications ne sont pas commitees."
  git status --short
  exit 1
fi

echo "== 4. le changelog documente-t-il $VERSION ? =="
# Meme controle que la CI, joue en local d'abord.
NOTES="$(python3 scripts/extract_changelog.py "$VERSION")"
echo "$NOTES" | sed 's/^/   | /'

echo "== 5. a jour avec origin ? =="
git fetch --quiet origin
BRANCHE="$(git rev-parse --abbrev-ref HEAD)"
if [ -n "$(git rev-list "origin/$BRANCHE..HEAD" 2>/dev/null)" ]; then
  echo "ECHEC : des commits locaux ne sont pas pousses. « git push » d'abord."
  exit 1
fi

echo
echo "Pret a publier $TAG depuis $BRANCHE ($(git rev-parse --short HEAD))."
read -r -p "Confirmer ? [o/N] " reponse
[[ "$reponse" =~ ^[oOyY]$ ]] || { echo "annule."; exit 0; }

git tag -a "$TAG" -m "$TAG

$NOTES"
git push origin "$TAG"

echo
echo "Etiquette $TAG poussee. GitHub construit la release."
echo "  Suivi CI : gh run watch"
echo "  La VM 110 la tirera dans les 2 minutes qui suivent la publication,"
echo "  si elle est allumee. Suivre : ssh adrien@192.168.0.32 'journalctl -t climbcontest-deploy -f'"
