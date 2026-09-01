# Spec 021 — La console se relit : clair/sombre, tiroir épinglé, page Classeur

> **Statut : rédigée, en attente de la porte 2.**
> Cinq remarques d'Adrien du 01/09/2026 au soir, après avoir piloté la console
> pour de vrai. Elles portent toutes sur la même surface — l'écran
> d'administration — et se recoupent : elles tiennent dans une seule spec.
>
> Trois points tranchés par Adrien avant rédaction :
> - confirmer un geste destructeur = **maintenir le bouton appuyé**, pas frapper
>   un mot ;
> - le thème suit le **système** (clair ou sombre), il ne se choisit pas dans la
>   console ;
> - l'accent est celui du **logo du club**. ⚠️ Correction de ma part : ce logo
>   n'a ni vert ni bleu — c'est un ocre/or (`#C8862A`, `#E0A94A`) sur charbon et
>   blanc os. C'est cet ocre qui est repris.

## 1. Ce qui cloche

### M1 — La page Classeur porte deux noms

Le tiroir annonce **« Classeur »**. La barre du haut et le `<h1>` disent
**« Classeur Google »**. C'est le même écran. Un menu qui ne mène pas au titre
qu'il annonce fait douter d'avoir cliqué au bon endroit, et ce doute coûte le
plus cher le matin d'une compétition, quand on cherche vite.

### M2 — « Importer le classeur » existe deux fois, et le plus visible est le plus faible

| Où | Ce que le bouton fait |
| --- | --- |
| Vue **Classeur**, carte « Où vont les réussites » | `POST /admin/import/sheet` **sans mode** — donc mise à jour implicite |
| Vue **Compétition**, carte « Importer le classeur » | le même appel, avec le **choix explicite** entre mise à jour et remplacement, et son rapport |

Deux boutons, le même libellé, deux comportements. Celui qui ne demande rien est
posé au milieu de l'écran qu'on ouvre pour régler le classeur ; celui qui fait
choisir est rangé dans une autre vue. C'est l'inverse de ce qu'il faut.

Et la carte du dessous, « Relier un autre classeur », porte déjà tout ce qu'il
faut pour brancher une feuille et repartir. Le bouton du haut n'apporte rien à
cet écran.

### M3 — Confirmer une destruction, c'est frapper « EFFACER » au clavier

Les trois gestes destructeurs — effacer les données, importer en remplacement,
supprimer une archive — passent par la même fenêtre, qui demande de **taper le
mot `EFFACER`**. Sept caractères, au clavier, sur un ordinateur portable posé sur
un coin de table dans une salle d'escalade. Adrien : « je déteste écrire ».

Le mot n'est pas là pour rien : il force à s'arrêter. Ce qu'il faut, c'est garder
**l'arrêt** et jeter **la frappe**.

### M4 — Le tiroir se referme même quand l'écran est immense

Le tiroir recouvre le contenu et se referme au premier clic — un choix assumé du
30/08, pensé pour le téléphone (« on l'ouvre, on fait UNE chose, on referme »).
Sur un écran de bureau de 1920 px, il reste 1600 px vides à droite du tiroir : le
recouvrir puis le refermer n'a plus aucun sens, et oblige à rouvrir le menu à
chaque changement de vue.

### M5 — La console impose son fond sombre

Les couleurs sont figées en dur dans `:root` : fond `#0D0F14`, accent mauve. La
page ne regarde pas `prefers-color-scheme`. Sur un Mac réglé en clair, en plein
jour, dans une salle éclairée, on lit un écran noir sans l'avoir demandé.

## 2. Ce qu'on fait

### F1 — La page s'appelle « Classeur »

Trois endroits, un seul nom : l'entrée du tiroir (déjà bonne), `VUES.classeur.titre`
et le `<h1>`. Le sous-titre continue de dire que c'est la feuille Google — c'est
là que l'information a sa place, pas dans le titre.

### F2 — Le bouton « Importer le classeur » quitte la vue Classeur

La carte « Où vont les réussites » garde **deux** actions : « Ouvrir le classeur »
et « Tester l'accès ». Les deux ne font que lire, ce qui rend la carte
homogène — on peut y cliquer sans réfléchir.

Le paragraphe qui expliquait « Importer » est remplacé par une phrase courte qui
**renvoie** vers l'endroit du geste : *« Importer les grimpeurs et les blocs se
fait depuis Compétition → Importer le classeur, avec le choix du mode. »* Un
bouton de navigation, pas d'action.

Rien ne change côté serveur : `POST /admin/import/sheet` reste, la vue
Compétition continue de l'appeler.

### F3 — Confirmer, c'est maintenir le bouton deux secondes

Dans la fenêtre partagée, le champ « Écris EFFACER » disparaît. Le bouton rouge
devient un **bouton à maintenir** :

- au contact (souris, doigt, ou **Entrée/Espace** au clavier), une **jauge**
  traverse le bouton en 2 s et le libellé passe à « Maintiens… » ;
- relâcher avant la fin **annule** — la jauge se vide d'un coup, rien n'est
  envoyé ;
- au bout des 2 s, le geste part.

Le libellé nomme l'acte et son volume : « Effacer les 100 participants », pas
« Effacer ». C'est ce chiffre, sous les yeux au moment du geste, qui remplace la
frappe comme dernier garde-fou.

La case « Effacer quand même » (compétition marquée en cours) est **conservée** :
elle dit autre chose que la confirmation — « je sais que le statut dit en
cours » — et elle reste obligatoire quand elle apparaît.

**Côté serveur, rien ne bouge.** `cycle.exiger_confirmation()` continue d'exiger
`confirmation: "EFFACER"` dans le corps JSON, et la console l'envoie une fois le
maintien abouti. Le mot cesse d'être un geste humain pour devenir un **marqueur
de protocole** : il protège toujours contre un `POST` nu, un onglet resté ouvert
ou un script qui appellerait la route sans passer par la fenêtre. Le docstring et
le message d'erreur, qui parlent aujourd'hui d'un mot « frappé à la main », sont
réécrits pour dire la vérité.

### F4 — Le tiroir reste ouvert quand l'écran le permet

À partir de **1080 px** de large, le tiroir est **épinglé** :

| | < 1080 px | ≥ 1080 px |
| --- | --- | --- |
| Tiroir | recouvre, fermé par défaut | **toujours ouvert**, dans le flux |
| Voile | oui | non |
| Burger | visible | **masqué** |
| Contenu | pleine largeur | décalé de la largeur du tiroir |
| Clic sur une entrée | change de vue **et referme** | change de vue, le tiroir reste |
| Échap | ferme | ne fait rien |

1080 px = les 310 px du tiroir + les 940 px de `main` moins ce que `main` peut
céder sans gêner. En dessous, le contenu deviendrait plus étroit que sur un
téléphone posé en travers : c'est là que le recouvrement reprend la main.

Le seuil est une **media query**, pas un test JavaScript : la mise en page ne
doit pas attendre l'exécution d'un script, et redimensionner la fenêtre doit
basculer sans rien recalculer à la main.

### F5 — Clair ou sombre, selon le système, en ocre du club

Toutes les couleurs passent par des variables CSS. Le thème clair devient le
thème **par défaut** ; le sombre est redéfini sous
`@media (prefers-color-scheme: dark)`. Aucun réglage dans la console : le
système décide, et c'est tout.

| Rôle | Clair | Sombre |
| --- | --- | --- |
| Fond | `#FBFAF8` blanc os | `#14130F` |
| Surface (cartes) | `#FFFFFF` | `#1D1B16` |
| Encre | `#1B1A17` charbon | `#F2EFE8` |
| Accent (aplats, boutons) | `#B5761C` | `#E0A94A` |
| Accent (texte et liens) | `#8A5A0F` | `#E8BC70` |
| Alerte / OK / Attention | `#B3392A` / `#2E7D4F` / `#9A6B0B` | `#F08A78` / `#6FC08A` / `#E5B44A` |

L'ocre vient des cornes du bouc et du mousqueton du logo. Il garde la fonction
que le mauve remplissait — **distinguer d'un coup d'œil la console de la page
publique projetée**, qui reste bleue — sans être une couleur choisie au hasard.

Les deux jeux respectent 4,5:1 sur le texte et 3:1 sur les bordures et les
états. C'est pour ça que l'accent « texte » diffère de l'accent « aplat » : l'or
du logo est trop clair pour écrire dessus en blanc, et trop clair pour écrire
avec sur du blanc.

`color-scheme: light dark` est déclaré sur `:root` — sans lui, les cases à
cocher, les `<dialog>` et les barres de défilement natives restent claires sur
un fond sombre.

### F6 — Les classements affichés se règlent à l'interrupteur

*Demandé par Adrien pendant l'implémentation.*

La carte « Ce qu'affiche la page de résultats » alignait des **cases à cocher**.
Une case à cocher dit « je consens » ; ces lignes-là disent « ce classement est
allumé ou éteint ». Ce n'est pas la même question, et l'**interrupteur** des
réglages qu'on a dans les mains toute la journée la pose mieux.

La case à cocher **native est conservée**, seulement rendue invisible : elle
garde le clavier, le focus, l'état et le lecteur d'écran — `role="switch"` la
fait annoncer « interrupteur, activé » plutôt que « case à cocher, cochée ». Le
visuel est un **frère** (`input:checked + .glissiere`), jamais un
pseudo-élément posé sur l'`<input>` : un `::after` sur un élément remplacé tient
de la tolérance des navigateurs, et cette console doit marcher le matin d'une
compétition, pas « en général ».

Le texte d'aide suit : « **Éteins** un classement pour le retirer » — « décoche »
ne veut plus rien dire quand il n'y a plus de case.

## 3. Périmètre

**Inclus** : `admin.html` uniquement (structure, style, script), et les deux
docstrings de `cycle.py` que F3 rend faux.

**Exclu, à dessein** :

- la page de résultats (`resultats.html`) et l'app juge — elles ont leurs
  propres contraintes de projection et d'extérieur, et l'ocre n'y a rien à
  faire tant que la spec 016 n'est pas rejugée ;
- un sélecteur de thème dans la console : le système décide (tranché) ;
- le contrat HTTP : aucune route, aucun corps JSON, aucun code de retour ne
  change.

## 4. Critères d'acceptation

**Tous vérifiés le 01/09/2026** — 31 tests Python (`tests/test_console_lisible.py`)
et 36 vérifications pilotées dans un vrai Chrome.

- [x] **A1** — Le tiroir, la barre et le `<h1>` disent tous « Classeur ».
- [x] **A2** — La carte « Où vont les réussites » n'a plus de bouton
  « Importer le classeur » ; elle renvoie en toutes lettres vers
  Compétition → Importer.
- [x] **A3** — `POST /admin/import/sheet` répond exactement comme avant depuis
  la vue Compétition (non-régression).
- [x] **A4** — La fenêtre de confirmation n'a plus de champ texte.
- [x] **A5** — Maintenir le bouton 2 s déclenche le geste ; relâcher à 1 s ne
  déclenche rien et laisse la fenêtre ouverte.
- [x] **A6** — Le maintien marche au clavier (Entrée ou Espace maintenus sur le
  bouton focalisé) et le bouton porte `aria-describedby` disant ce qu'il faut
  faire.
- [x] **A7** — Le libellé du bouton nomme le volume détruit (« Effacer les 100
  participants »).
- [x] **A8** — La case « Effacer quand même » reste obligatoire quand la
  compétition est marquée en cours ; sans elle, le maintien n'active rien.
- [x] **A9** — `POST /admin/effacer` sans `confirmation` répond toujours 400 et
  ne touche à rien (non-régression).
- [x] **A10** — À 1280 px, le tiroir est ouvert, sans voile, sans burger, et le
  contenu n'est pas recouvert.
- [x] **A11** — À 900 px, le tiroir est fermé, le burger est là, et le
  comportement est celui d'aujourd'hui.
- [x] **A12** — À 1280 px, cliquer une entrée du tiroir change de vue **sans**
  refermer le tiroir.
- [x] **A13** — En thème clair, aucune couleur n'est écrite en dur hors des
  variables `:root` ; le contraste texte/fond est ≥ 4,5:1 partout.
- [x] **A14** — Basculer le système clair→sombre change la page sans rechargement
  et sans réglage dans la console.
- [x] **A15** — Les classements affichés sont des interrupteurs, pilotables à la
  souris **et** au clavier, annoncés `switch`, et l'état survit à un
  enregistrement suivi d'un rechargement.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Redimensionner la fenêtre de 1400 à 800 px, tiroir épinglé | Le tiroir se replie et redevient recouvrant ; aucun état JavaScript ne reste coincé |
| Redimensionner de 800 (tiroir **ouvert**) à 1400 px | Le tiroir reste ouvert, épinglé ; le voile disparaît |
| Redimensionner de 800 (tiroir **fermé**) à 1400 px | Le tiroir apparaît ouvert : c'est la media query qui décide, pas la dernière action |
| Maintien interrompu par un `Échap` | La fenêtre se ferme, rien n'est envoyé |
| Maintien avec la souris, curseur sorti du bouton avant la fin | Annulé — même règle que relâcher |
| Deux maintiens successifs très rapides | Un seul envoi : le bouton se désactive dès le premier départ |
| `prefers-reduced-motion` | La jauge disparaît ; le libellé « Maintiens… » porte seul l'information. La temporisation de 2 s **ne change pas** : c'est une garde, pas une décoration |
| Système sans `prefers-color-scheme` (vieux navigateur) | Thème **clair** — c'est le défaut, il ne dépend d'aucune requête média |
| Le jour J, la console plante au chargement du style | Aucune conséquence : tout est en ligne dans le fichier, il n'y a rien à télécharger |

## 6. Ce que l'implémentation a corrigé en plus

**Les cases à cocher étaient étirées sur toute la largeur de leur carte**, leur
libellé rejeté hors du cadre. La règle globale `input, select, textarea` leur
donnait `width: 100%`, un fond, une bordure et 10 px de rembourrage — elle n'a
jamais distingué un champ de saisie d'une case à cocher.

Deux endroits en souffraient, et le second est celui qu'Adrien a signalé pendant
l'implémentation : **« Ce qu'affiche la page de résultats »**, où les catégories
sortaient du cadre, et la case « Effacer quand même » de la fenêtre de
confirmation. Un seul défaut, corrigé **à la racine** — la règle exclut désormais
`[type="checkbox"]` et `[type="radio"]` — plutôt que carte par carte. Les deux
rustines locales qui redisaient `width: auto` ont disparu avec lui.

**Le libellé anneau → jauge.** Un anneau sur un bouton rectangulaire est
malcommode ; une jauge qui traverse le bouton dit « continue d'appuyer » bien
plus clairement. La spec a été corrigée, pas contournée.
