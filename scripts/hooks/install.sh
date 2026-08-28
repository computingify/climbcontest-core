#!/bin/bash
# Installe les hooks git du depot. A relancer apres un clone.
set -e
RACINE="$(git rev-parse --show-toplevel)"
install -m 0755 "$RACINE/scripts/hooks/pre-commit" "$RACINE/.git/hooks/pre-commit"
echo "hook pre-commit installe."
command -v gitleaks >/dev/null 2>&1 || echo "ATTENTION : gitleaks n'est pas installe (brew install gitleaks) — le hook sera inoperant."
