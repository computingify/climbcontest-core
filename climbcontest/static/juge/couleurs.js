/**
 * Les couleurs de circuit — les MÊMES que l'application Android
 * (ui/theme/Color.kt). Deux clients, une seule identité.
 *
 * ⚠️ La couleur PORTE DE L'INFORMATION : un juge lit la couleur de l'écran
 * pour vérifier qu'il est sur le bon circuit — ce que le tag seul (« ZJ1 »)
 * ne dit pas à quelqu'un qui ne connaît pas la convention de nommage.
 */

export const CIRCUITS = {
  jaune: "#F5B72E",
  vert: "#34C56A",
  bleu: "#3E8CF7",
  mauve: "#A86CF0",
  violet: "#A86CF0",     // le classeur écrit parfois « violet »
  rouge: "#F0554A",
  // Le circuit « Noir » est rendu en CRAIE : un aplat noir sur un fond
  // presque noir ne se verrait pas, et le juge ne saurait pas s'il a scanné.
  noir: "#E8EBF0",
};

/**
 * La couleur d'un circuit, telle que le serveur la nomme.
 *
 * Insensible à la casse et aux espaces. Rend `null` pour un nom inconnu :
 * un circuit dont on ne connaît pas la couleur ne doit pas empêcher de
 * valider une réussite — l'écran reste alors sur sa teinte neutre.
 */
export function couleurDeCircuit(nom) {
  if (typeof nom !== "string") return null;
  return CIRCUITS[nom.trim().toLowerCase()] || null;
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
