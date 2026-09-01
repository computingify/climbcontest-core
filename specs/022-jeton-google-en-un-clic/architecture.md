# Architecture — 022 jeton-google-en-un-clic

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/sheets/consentement.py` | **Nouveau** — tout le flux OAuth, sans Flask sauf la session |
| `climbcontest/sheets/client.py` | `chemin_credentials()`, `etat_credentials()`, et le message d'erreur de F5 |
| `climbcontest/routes/admin.py` | Deux routes, et `base_publique()` extrait de `lien_juge()` |
| `climbcontest/templates/admin.html` | La carte « Jeton Google » |
| `docs/runbook-competition.md` | La manip Google de F4 |
| `docs/technical/classeur-google.md` | § 5 ter : le tableau des trois formes de jeton gagne l'origine « console (OAuth) » |
| `tests/test_consentement_google.py` | **Nouveau** |

Aucun modèle, aucune migration. `google-auth-oauthlib==1.2.1` est **déjà** dans
`requirements.txt` : rien à ajouter.

## Le flux

```
 console                     backend                        Google
    │                           │                              │
    │ clic « Connecter »        │                              │
    ├──────────────────────────▶│ GET /admin/classeur/         │
    │                           │     google/consentement      │
    │                           │  state = secrets.token_urlsafe(32)
    │                           │  session["google_state"] = state
    │                           │  302 ─────────────────────────▶ écran de consentement
    │                                                          │
    │◀─────────── 302 vers /admin/classeur/google/retour?code&state
    │                           │                              │
    │                           │ vérifie state (comparaison   │
    │                           │  à temps constant), pop      │
    │                           │ fetch_token(code) ──────────▶│
    │                           │◀───────── credentials ───────│
    │                           │ refuse si pas de refresh_token
    │                           │ ecrire_jeton_json(creds.to_json())
    │◀── 302 /console?jeton=pose│                              │
```

`state` est **retiré** de la session dès la première lecture : un code d'autori-
sation ne se rejoue pas, et le `state` non plus.

## `sheets/consentement.py`

Aucun import Flask hors `session` — comme `cycle.py` et `circuits.py`, le module
se teste sans client HTTP.

```python
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def disponible() -> dict          # {"pret", "chemin", "message"} — credentials.json ?
def url_de_consentement(uri_retour: str) -> tuple[str, str]   # (url, state)
def echanger(code: str, uri_retour: str) -> str               # → le JSON du jeton
```

- `url_de_consentement` construit un `google_auth_oauthlib.flow.Flow` depuis
  `credentials.json`, `access_type="offline"`, `prompt="consent"`,
  `include_granted_scopes="true"`.
- `echanger` refuse et **lève** si le jeton rendu n'a pas de `refresh_token` :
  la même garde que `parametrage.poser_jeton()`, pour la même raison — un jeton
  sans rafraîchissement meurt à la première expiration, et la panne se découvre
  le lendemain matin.
- Aucune écriture ici : `echanger` rend une chaîne, la route appelle
  `ecrire_jeton_json`. La séparation permet de tester l'échange sans toucher au
  disque.

## Les routes

```python
@bp.get("/classeur/google/consentement")
@exige_role(ADMIN)
def google_consentement():
    """302 vers Google. Le state part en session, jamais dans une reponse."""

@bp.get("/classeur/google/retour")
@exige_role(ADMIN)
def google_retour():
    """Le retour de Google. Ecrit le jeton, puis 302 vers /console."""
```

Elles **redirigent**, elles ne rendent pas de JSON : c'est une navigation de
page entière, la seule chose que Google accepte. Le résultat revient à la
console dans la requête (`/console?jeton=pose`, `?jeton=refuse`,
`?jeton=erreur&d=<code court>`), jamais dans le fragment — la console lit
`location.search`, affiche le message et **nettoie l'URL** avec
`history.replaceState`.

⚠️ Le code d'erreur passé dans l'URL est un **code court** de notre cru
(`etat`, `sans_refresh`, `ecriture`), jamais le message brut de Google : on ne
recopie pas dans une URL ce qu'un tiers nous a envoyé.

`SESSION_COOKIE_SAMESITE = "Lax"` laisse passer le cookie sur ce retour — c'est
une navigation GET de premier niveau. En `Strict`, la session serait perdue au
retour ; c'est une raison de plus de ne pas y toucher.

## L'URI de retour

Elle doit être **au caractère près** celle déclarée chez Google. Elle est donc
construite une seule fois, par la règle qui existe déjà dans `lien_juge()` —
extraite en fonction et partagée :

```python
def base_publique() -> str:
    """« https://climbcontest.adn-dev.fr ». Derriere Caddy, gunicorn voit du
    http : on force https sauf en developpement local. Pas de ProxyFix pour si
    peu -- et cette regle sert maintenant a DEUX endroits."""
```

La carte de la console **affiche** cette URI, prête à copier dans la Google
Cloud Console. C'est ce qui rend `redirect_uri_mismatch` réparable sans lire une
documentation.

## Ce que la carte affiche

`GET /admin/classeur` gagne, dans son objet `jeton`, deux champs :

```json
"jeton": {
  "present": true, "source": "json", "valide": true,
  "expire_le": "…", "scopes": ["…/spreadsheets"], "chemin": "…",
  "consentement": { "pret": true, "message": null,
                    "uri_retour": "https://climbcontest.adn-dev.fr/admin/classeur/google/retour" }
}
```

`pret: false` désactive le bouton et affiche `message` — critère A6. Rien
d'autre ne change dans la réponse : les consommateurs existants ne bougent pas.

## Sécurité

| Risque | Ce qui le couvre |
| --- | --- |
| CSRF sur le retour | `state` aléatoire de 32 octets, en session, comparé puis retiré |
| Jeton dans un journal | Rien du jeton ne transite par une URL ni par une réponse ; le journal note « jeton pose par <identifiant> », jamais le contenu |
| Jeton lisible sur disque | `_ecrire_atomique` en 0600, dossier des secrets hors des releases (inchangé) |
| Route ouverte | `@exige_role(ADMIN)` sur les deux, comme les quatre routes classeur existantes |
| Secret committé | `credentials.json` et `token.json` sont déjà dans `.gitignore` ; `gitleaks` tourne en CI |
| Code d'autorisation rejoué | `state` retiré à la première lecture, et Google refuse un code déjà échangé |
