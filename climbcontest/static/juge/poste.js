/**
 * Le QR posé sur la table du juge, et rien d'autre (spec 034).
 *
 * Le juge arrive à sa table, ouvre l'application, scanne le carton posé devant
 * lui : son téléphone s'appelle « Zone C ». Il n'a rien tapé.
 *
 * ⚠️ **LE PRÉFIXE EST LA RAISON D'ÊTRE DE CE MODULE.**
 *
 * Trois familles de QR circulent le jour J, et le même viseur les voit toutes :
 * le dossard (`42`), le bloc (`ZJ6`), le lien de l'organisateur
 * (`https://…/juge?j=…`). Sans préfixe, un juge qui scanne un bloc par erreur
 * depuis cet écran renommerait son poste « ZJ6 » **sans s'en apercevoir**, et
 * la console afficherait « ZJ6 » en face de tous ses envois de la journée.
 * Le préfixe rend la confusion *impossible*, pas improbable.
 *
 * ⚠️ **DU TEXTE BRUT, PAS UNE URL.** Une URL (`…/juge?poste=Zone+C`) scannée
 * par l'appareil photo NATIF du téléphone ouvre un navigateur : le juge se
 * retrouverait dans Safari, dans une deuxième instance sans file d'attente.
 * `CCPOSTE:Zone C` scanné au mauvais endroit ne fait rien — un échec propre et
 * sans conséquence, ce qu'on veut d'un geste fait par erreur.
 *
 * ⚠️ **LE PRÉFIXE EST ÉCRIT DEUX FOIS**, ici et dans `fiches.PREFIXE_QR_POSTE`
 * qui l'imprime. Le jour où les deux divergent, TOUS les QR imprimés cessent
 * d'être lus sans qu'une ligne ait l'air fausse. Un test Python lit ce fichier
 * et compare : voir `tests/test_postes.py::TestLePrefixePartage`.
 *
 * Aucun accès au DOM ni au réseau : ce module se teste sur Node, comme
 * `jeton.js` et `politique.js`.
 */
import { nettoyerLeNom } from "./identite.js";
import { jetonDUneAdresse } from "./jeton.js";

export const PREFIXE_POSTE = "CCPOSTE:";

/** Ce qu'on encode dans le QR d'une zone. Le pendant de `nomDePoste`. */
export function texteDuQrDePoste(zone) {
  return PREFIXE_POSTE + String(zone ?? "").trim();
}

/**
 * Le nom de poste porté par ce QR, ou `null` si ce n'en est pas un.
 *
 * Le préfixe se lit **sans tenir compte de la casse** : un QR refait à la main
 * ne doit pas devenir un QR mort. Il est toujours ÉCRIT en majuscules.
 *
 * Le nom passe par `nettoyerLeNom` — le même nettoyage que la saisie au
 * clavier. Une seule règle de nom pour les deux chemins, sinon un poste
 * scanné et le même poste tapé porteraient deux noms différents.
 *
 * `CCPOSTE:` sans rien derrière rend `null` : un renommage à vide est pire que
 * pas de renommage, parce qu'il efface un nom déjà réglé.
 */
export function nomDePoste(texte) {
  const brut = String(texte ?? "").trim();
  // On ne met en majuscules que les huit premiers caractères : `toUpperCase()`
  // peut changer la LONGUEUR d'une chaîne (« ß » → « SS »), et un décalage
  // d'index sur le reste du texte tronquerait le nom de la zone.
  if (brut.slice(0, PREFIXE_POSTE.length).toUpperCase() !== PREFIXE_POSTE) return null;
  return nettoyerLeNom(brut.slice(PREFIXE_POSTE.length));
}

/**
 * Pourquoi ce QR est refusé, en français et avec la marche à suivre.
 *
 * ⚠️ Trois messages, pas un. « QR invalide » enverrait le juge chercher un
 * organisateur dans les trois cas, alors qu'il tient parfois le BON QR au
 * mauvais endroit — et que dans un cas sur trois, c'est le carton lui-même qui
 * est en cause et qu'il faut effectivement le signaler.
 *
 * À n'appeler que lorsque `nomDePoste` a rendu `null`.
 */
export function expliquerLeQrRefuse(texte) {
  const brut = String(texte ?? "").trim();

  if (jetonDUneAdresse(brut)) {
    return "Ce QR est le lien de l’organisateur, pas le QR de ton poste. " +
           "Celui-là sert à installer l’application.";
  }
  if (brut.slice(0, PREFIXE_POSTE.length).toUpperCase() === PREFIXE_POSTE) {
    // Le carton porte bien un QR de poste, mais il est vide : c'est un défaut
    // d'impression, et le juge n'y peut rien.
    return "Ce QR de poste ne porte aucun nom de zone. Va voir un organisateur.";
  }
  return "Ce QR n’est pas un QR de poste. Le QR de poste est celui posé sur ta " +
         "table, avec le nom de la zone écrit en gros dessous.";
}
