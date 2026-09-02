/**
 * Les marches du podium de la page de résultats (specs 020, 027).
 *
 * Extrait du gabarit pour être TESTABLE : ces deux fonctions décidaient seules
 * de ce que le vidéoprojecteur montre à la remise des prix, et aucun test ne
 * les exécutait. Deux défauts y vivaient, tous deux invisibles à la lecture et
 * trouvés en rejouant la logique à la main.
 *
 *   node --test "tests/js/*.test.mjs"
 */

/** Au-delà, la marche devient un mur de noms illisible à dix mètres. */
export const MAXI_SUR_LE_PODIUM = 6;

/**
 * Qui monte sur le podium, et le podium s'affiche-t-il.
 *
 * ⚠️ Un grimpeur n'y monte que s'il a MARQUÉ. Sans ce filtre, une catégorie
 * qui n'a pas commencé met tout le monde au rang 1 et couronne dix-sept
 * personnes à zéro point.
 *
 * ⚠️ Au-delà de six, on MASQUE le podium au lieu de le vider. Le vider
 * affichait trois marches en pointillé — exactement le rendu d'une catégorie
 * où personne n'a marqué. Deux situations opposées, un seul dessin : l'écran
 * aurait annoncé « pas encore de gagnant » alors que sept personnes sont
 * premières. Masqué, le tableau reprend le relais et dit la vérité.
 */
export function selectionDuPodium(lignes, avecPodium) {
  const surLePodium = lignes.filter((l) => l.rang <= 3 && l.score > 0);
  if (surLePodium.length > MAXI_SUR_LE_PODIUM) return { podium: false, tete: [] };
  return { podium: avecPodium, tete: avecPodium ? surLePodium : [] };
}

/**
 * Une marche par RANG, et toujours trois tant que le podium est affiché.
 *
 * ⚠️ Un rang peut être ABSENT sans être LIBRE. Le classement saute les rangs
 * derrière un ex æquo — deux premiers, puis un troisième : il n'y a pas de
 * deuxième, et il n'y en aura jamais. Combler ce rang-là dessinait une marche
 * en pointillé, que la feuille de style définit comme « pas encore attribué ».
 * Le public lisait « la deuxième place n'est pas encore décidée » à la remise
 * des prix, devant deux ex æquo et un troisième.
 */
export function marchesDuPodium(tete, podium) {
  const marches = [];
  tete.forEach((l) => {
    const derniere = marches[marches.length - 1];
    if (derniere && derniere.rang === l.rang) derniere.lignes.push(l);
    else marches.push({ rang: l.rang, lignes: [l] });
  });

  if (podium) {
    const tenus = {};
    marches.forEach((m) => { tenus[m.rang] = true; });
    [1, 2, 3].forEach((rang) => {
      if (tenus[rang]) return;
      const absorbe = marches.some(
        (m) => m.rang < rang && m.rang + m.lignes.length > rang);
      if (!absorbe) marches.push({ rang, lignes: [], vide: true });
    });
    marches.sort((a, b) => a.rang - b.rang);
  }
  return marches;
}
