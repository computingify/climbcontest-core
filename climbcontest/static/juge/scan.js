/**
 * Lire un QR code, sur Safari comme sur Chrome.
 *
 * Deux chemins, et le second n'est pas un cas dégradé :
 *
 * - `BarcodeDetector`, natif, sur Chrome Android. Rapide, rien à télécharger.
 * - **jsQR**, sur Safari — donc sur tous les iPhone, c'est-à-dire exactement le
 *   public pour lequel cette PWA existe. Ce chemin est le principal, pas le
 *   repli, et c'est lui qu'il faut essayer en premier quand on teste.
 *
 * jsQR n'est chargé QUE si `BarcodeDetector` manque : sur Chrome Android, ces
 * 250 ko ne partent jamais sur le réseau.
 */

const TAILLE_ANALYSE = 640;   // on n'analyse pas plus grand : inutile, et lent

let jsQRCharge = null;

/** Charge jsQR une seule fois, et seulement si on en a besoin. */
function chargerJsQR() {
  if (jsQRCharge) return jsQRCharge;
  jsQRCharge = new Promise((resoudre, rejeter) => {
    const balise = document.createElement("script");
    balise.src = "/static/juge/jsqr.js";
    balise.onload = () => resoudre(window.jsQR);
    balise.onerror = () => rejeter(new Error("decodeur indisponible"));
    document.head.appendChild(balise);
  });
  return jsQRCharge;
}

/**
 * Pourquoi la caméra n'est pas accessible, en français et avec la marche à
 * suivre.
 *
 * « NotAllowedError » ne dit rien à un bénévole. Sur iPhone, l'autorisation se
 * redemande dans les réglages de Safari, pas dans la page — sans cette phrase,
 * le juge reste bloqué devant un écran noir.
 */
export function expliquerLErreurCamera(erreur) {
  const nom = erreur && erreur.name;
  if (nom === "NotAllowedError" || nom === "SecurityError") {
    return "Accès à la caméra refusé. Sur iPhone : Réglages → Safari → Caméra → " +
           "Autoriser, puis rouvre l'application.";
  }
  if (nom === "NotFoundError" || nom === "OverconstrainedError") {
    return "Aucune caméra arrière trouvée sur cet appareil.";
  }
  if (nom === "NotReadableError") {
    return "La caméra est déjà utilisée par une autre application. Ferme-la et réessaie.";
  }
  return "Impossible d'ouvrir la caméra.";
}

/**
 * Ouvre la caméra et rend le premier QR code lu.
 *
 * Rend `null` si l'appelant annule. Lève si la caméra est inaccessible — c'est
 * un cas que le juge doit voir, pas un `null` silencieux.
 */
export async function lireUnQr(video, signalAnnulation) {
  const flux = await navigator.mediaDevices.getUserMedia({
    // `environment` : la caméra arrière. Sans ça, un iPhone ouvre la caméra
    // avant, et le juge se filme au lieu de scanner.
    video: { facingMode: { ideal: "environment" } },
    audio: false,
  });

  video.srcObject = flux;
  // `playsinline` dans le HTML ET ce `play()` : sans les deux, Safari iOS ouvre
  // la vidéo en plein écran natif, par-dessus l'application.
  await video.play();

  try {
    return await boucleDeLecture(video, signalAnnulation);
  } finally {
    // Toujours, y compris si l'appelant annule ou si ça lève : une caméra
    // laissée ouverte vide la batterie et laisse la pastille allumée.
    flux.getTracks().forEach((piste) => piste.stop());
    video.srcObject = null;
  }
}

async function boucleDeLecture(video, signalAnnulation) {
  const detecteur = "BarcodeDetector" in window
    ? new window.BarcodeDetector({ formats: ["qr_code"] })
    : null;
  const jsQR = detecteur ? null : await chargerJsQR();

  const toile = document.createElement("canvas");
  const contexte = toile.getContext("2d", { willReadFrequently: true });

  while (!signalAnnulation.aborted) {
    if (video.readyState >= 2 && video.videoWidth > 0) {
      let texte = null;
      if (detecteur) {
        const trouves = await detecteur.detect(video).catch(() => []);
        texte = trouves.length ? trouves[0].rawValue : null;
      } else {
        texte = lireAvecJsQR(jsQR, video, toile, contexte);
      }
      if (texte) return texte.trim();
    }
    await new Promise((r) => requestAnimationFrame(r));
  }
  return null;
}

function lireAvecJsQR(jsQR, video, toile, contexte) {
  // On réduit avant d'analyser : jsQR travaille sur les pixels, et analyser une
  // image 4K à chaque trame ferait chauffer le téléphone pour rien.
  const echelle = Math.min(1, TAILLE_ANALYSE / Math.max(video.videoWidth, video.videoHeight));
  toile.width = Math.round(video.videoWidth * echelle);
  toile.height = Math.round(video.videoHeight * echelle);
  contexte.drawImage(video, 0, 0, toile.width, toile.height);
  const image = contexte.getImageData(0, 0, toile.width, toile.height);
  const trouve = jsQR(image.data, image.width, image.height, {
    inversionAttempts: "dontInvert",   // nos QR sont noirs sur blanc
  });
  return trouve ? trouve.data : null;
}
