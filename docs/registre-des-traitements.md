# Registre des traitements

Document exigé par l'**article 30 du RGPD**, y compris pour une petite
association. Il n'a pas à être publié : il doit exister, être à jour, et
pouvoir être présenté.

**Responsable de traitement** : le club organisateur de la compétition.
**Contact** : `adrien.jouve@adn-dev.fr`.
**Dernière mise à jour** : 4 septembre 2026 (spec 043).

⚠️ Ce registre décrit **ClimbContest**. La badgeuse des séances du club
(`climbBackEnd`) est hors périmètre et relève de son propre registre.

---

## 1. Inscriptions

| | |
| --- | --- |
| **Finalité** | Inscrire les grimpeurs à une compétition, constituer les catégories, imprimer les dossards |
| **Base légale** | Exécution d'une mesure précontractuelle et intérêt légitime du club (art. 6.1.b et 6.1.f) |
| **Personnes concernées** | Grimpeurs inscrits, **dont une majorité de mineurs** |
| **Données** | Nom, prénom, club, catégorie, numéro de dossard. Selon l'origine de l'inscription : année de naissance et genre |
| **Origine** | Classeur Google de la compétition, saisie sur place depuis la console, et — à terme — formulaire HelloAsso |
| **Destinataires** | Les organisateurs du club. Le classeur Google est hébergé par Google (Google Workspace) |
| **Conservation** | Le temps de la compétition, puis dans les archives du club |
| **Sécurité** | HTTPS ; console réservée aux comptes organisateurs, avec rôles et frein anti-force-brute ; accès au classeur par jeton OAuth stocké hors dépôt |

## 2. Déroulement de la compétition

| | |
| --- | --- |
| **Finalité** | Enregistrer les blocs réussis, calculer les classements, tracer les envois des juges |
| **Base légale** | Intérêt légitime : sans cela, il n'y a pas de compétition (art. 6.1.f) |
| **Personnes concernées** | Grimpeurs inscrits ; juges bénévoles |
| **Données** | Réussites (grimpeur × bloc × horodatage), et pour la traçabilité : nom donné au téléphone du juge, code court de l'appareil, référence du scan |
| **Destinataires** | Les organisateurs. Les téléphones des juges reçoivent un catalogue **volontairement maigre** — nom, dossard, club, catégorie — et rien d'autre |
| **Conservation** | Le temps de la compétition, puis dans l'archive de l'édition |
| **Sécurité** | Clé d'API exigée des applications juges ; le jeton d'un juge est filtré des journaux du proxy ; base sur une machine du réseau local, sauvegardée |

## 3. Publication des résultats

| | |
| --- | --- |
| **Finalité** | Afficher le classement en direct dans la salle et sur les téléphones des spectateurs |
| **Base légale** | Intérêt légitime (art. 6.1.f) — publier les résultats est l'objet de la compétition. **Assorti d'un droit d'opposition simple**, sans quoi cette base ne tiendrait pas |
| **Personnes concernées** | Grimpeurs figurant à un classement |
| **Données publiées** | Nom, prénom, club, catégorie, dossard, rang, score, nombre de blocs. **Rien d'autre** : ni adresse, ni téléphone, ni date de naissance, ni photographie |
| **Destinataires** | Toute personne disposant de l'adresse de la page |
| **Conservation** | Les résultats de l'édition en cours restent en ligne. Les éditions archivées **ne sont pas publiques** : elles ne sont servies qu'après connexion d'un organisateur |
| **Sécurité et limitation** | Aucune indexation par les moteurs de recherche (`robots.txt`, `noindex`, `X-Robots-Tag`) ; mention et page d'information accessibles depuis la page de résultats ; **droit d'opposition exerçable** — la ligne reste au classement, le nom devient « Dossard N » |

---

## Droits des personnes

Accès, rectification, effacement, opposition — par courriel à
`adrien.jouve@adn-dev.fr`, réponse due sous **un mois**. Les données collectées
lorsque la personne était **mineure** relèvent de l'effacement renforcé
(art. 17 RGPD, art. 51 de la loi 78-17) : traitement dans les meilleurs délais.
Recours possible auprès de la CNIL.

Le chemin public de ces droits est la page `/confidentialite`, atteignable
depuis la page de résultats.

## Ce que ce registre ne couvre pas encore

- **La durée de conservation des archives n'est pas bornée.** Écartée du
  périmètre de la spec 043 par décision du 04/09 ; l'article 5.1.e la demande,
  et l'étude
  [du 4 septembre](rapports/2026-09-04-donnees-personnelles-resultats.html)
  en décrit la mise en œuvre le jour où elle est décidée.
- **La politique de confidentialité du Play Store**
  (dépôt `climbcontestConfidentiality`) ne décrit que l'application juge et
  affirme qu'aucune donnée personnelle n'est collectée — exact pour le juge,
  faux pour le système. Sa réécriture reste à faire.
