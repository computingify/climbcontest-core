/**
 * Les couleurs de circuit — les MÊMES que l'application Android
 * (ui/theme/Color.kt). Deux clients, une seule identité sur ce qui porte de
 * l'information.
 *
 * ⚠️ Une exception depuis la spec 039 : le circuit « Noir ». La PWA s'ouvre en
 * clair, l'Android est restée sombre, et « Noir » est le seul circuit dont le
 * rendu dépend du fond. Les cinq autres sont identiques au pixel.
 *
 * ⚠️ La couleur PORTE DE L'INFORMATION : un juge lit la couleur de l'écran
 * pour vérifier qu'il est sur le bon circuit — ce que le tag seul (« ZJ1 »)
 * ne dit pas à quelqu'un qui ne connaît pas la convention de nommage.
 */


/**
 * Le circuit « Noir », qui dépend du THÈME — le seul de la famille.
 *
 * Un aplat noir sur un fond presque noir ne se voit pas : le juge ne saurait
 * pas s'il a scanné. C'est pour ça qu'il était rendu en CRAIE. Mais la craie
 * était une rustine du fond sombre, et depuis la spec 039 la PWA s'ouvre en
 * CLAIR : sur du papier sable, un aplat craie ne se voit pas davantage.
 *
 * Les cinq autres circuits n'ont pas ce problème — leur teinte est franche et
 * tient sur les deux fonds. « Noir », lui, prend l'encre du thème : presque
 * noir sur le papier, craie sur l'ardoise. Dans les deux cas c'est la couleur
 * la plus contrastée de l'écran, ce que « Noir » veut dire dans une salle.
 */
export const NOIR = { clair: "#22201B", sombre: "#E8EBF0" };

export const CIRCUITS = {
  jaune: "#F5B72E",
  vert: "#34C56A",
  bleu: "#3E8CF7",
  mauve: "#A86CF0",
  violet: "#A86CF0",     // le classeur écrit parfois « violet »
  rouge: "#F0554A",
  // Le seul qui dépend du thème, et sa valeur claire est le défaut : voir
  // NOIR juste au-dessus, et `couleurDeCircuit`.
  noir: NOIR.clair,
};

/**
 * Le thème du téléphone, à l'instant où on le demande.
 *
 * ⚠️ Hors navigateur — les tests de `tests/js/` tournent sous Node — il n'y a
 * pas de `matchMedia`, et la réponse est CLAIR : c'est le défaut de
 * l'application, pas une valeur de repli arbitraire.
 */
export function enSombre() {
  return typeof globalThis.matchMedia === "function"
    && globalThis.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * La couleur d'un circuit, telle que le serveur la nomme.
 *
 * Insensible à la casse et aux espaces. `sombre` ne sert qu'au circuit
 * « Noir » (voir NOIR) ; les cinq autres teintes ne dépendent pas du thème.
 *
 * Rend `null` pour un nom inconnu :
 * un circuit dont on ne connaît pas la couleur ne doit pas empêcher de
 * valider une réussite — l'écran reste alors sur sa teinte neutre.
 */
export function couleurDeCircuit(nom, sombre = enSombre()) {
  if (typeof nom !== "string") return null;
  const cle = nom.trim().toLowerCase();
  if (cle === "noir") return sombre ? NOIR.sombre : NOIR.clair;
  return CIRCUITS[cle] || null;
}

/**
 * Est-ce le circuit « Noir » ? — la question que le CSS ne peut pas poser.
 *
 * Depuis la spec 041, la carte du bloc scanné est teintée de son circuit et
 * cerclée d'encre. Sur « Noir », la teinte EST l'encre : la carte vire au gris
 * et le liseré se confond avec l'aplat. Le CSS ne sait pas comparer deux
 * couleurs, il lui faut donc un marqueur — et ce marqueur se déduit du NOM,
 * jamais de la valeur : `NOIR.clair` et `--encre` sont deux constantes
 * distinctes, qui peuvent diverger d'un point sans cesser de désigner
 * la même chose.
 *
 * Mêmes règles de lecture que `couleurDeCircuit` : la casse et les espaces
 * restent sans effet, un nom qui n'est pas une chaîne rend `false`.
 */
export function estLeNoir(nom) {
  return typeof nom === "string" && nom.trim().toLowerCase() === "noir";
}

/**
 * Du texte lisible sur n'importe quelle couleur de circuit — la luminance
 * décide, comme côté Android. Jaune et craie demandent de l'encre sombre.
 */
export function encreSur(hex) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16 & 255) / 255, v = (n >> 8 & 255) / 255, b = (n & 255) / 255;
  const luminance = 0.2126 * r + 0.7152 * v + 0.0722 * b;
  return luminance > 0.55 ? "#12140F" : "#F7F9FC";
}
