"""La fiche du grimpeur en direct — spec 026, côté serveur.

Trois choses se vérifient ici, et elles ne sont pas de même nature :

1. **Les trois ensembles du moteur sont disjoints.** C'est une garantie de
   contrat, pas une observation : la page peint l'union de deux d'entre eux et
   afficherait le même bloc deux fois, dans deux états contraires, si elle
   tombait.
2. **La fiche dit ce qui manque au lieu de disparaître.** Un circuit inconnu,
   une catégorie absente : la fiche se rend quand même.
3. **Le plan servi est versionné et sans grimpeur.** C'est ce qui permet à la
   page de le refuser proprement le jour où sa forme change.
"""
import json
import re

import pytest

from climbcontest.classement_service import blocs_du_grimpeur, invalider
from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Participant, Success
from climbcontest.suivi import CREDITE, FORMAT_PLAN, GRIMPE, RESTE, fiche, plan_public


def reussite(participant, bloc):
    db.session.add(Success(participant_id=participant.id, bloc_id=bloc.id))
    db.session.commit()
    invalider()


class TestLesTroisEnsembles:
    """`blocs_du_grimpeur` — le seul accesseur, et son contrat."""

    def test_une_reussite_du_circuit_est_grimpee(self, jeu):
        lea, zj6 = jeu["participants"][0], jeu["blocs"][0]
        reussite(lea, zj6)
        etats = blocs_du_grimpeur(jeu["competition"], lea)
        assert etats["grimpes"] == {zj6.id}
        assert etats["credites"] == set()
        assert etats["hors_circuit"] == set()

    def test_une_reussite_hors_circuit_ne_compte_pas(self, jeu):
        """DV21 est du circuit U13 ; Léa est en U11 F.

        La réussite existe — un juge l'a vue et a forcé l'avertissement de la
        spec 019 — mais elle ne rejoint jamais `grimpes`.
        """
        lea, dv21 = jeu["participants"][0], jeu["blocs"][2]
        reussite(lea, dv21)
        etats = blocs_du_grimpeur(jeu["competition"], lea)
        assert etats["grimpes"] == set()
        assert etats["hors_circuit"] == {dv21.id}

    def test_sans_categorie_aucun_bloc_ne_compte(self, jeu):
        """Un grimpeur sans catégorie n'a pas de circuit : tout est hors."""
        orphelin = Participant(competition_id=jeu["competition"].id,
                               nom="Sans", prenom="Categorie", dossard=99)
        db.session.add(orphelin)
        db.session.commit()
        reussite(orphelin, jeu["blocs"][0])
        etats = blocs_du_grimpeur(jeu["competition"], orphelin)
        assert etats["grimpes"] == set()
        assert etats["hors_circuit"] == {jeu["blocs"][0].id}

    def test_les_trois_ensembles_sont_disjoints(self, jeu):
        """La garantie dont dépend l'affichage, vérifiée sur tous les cas.

        Deux à deux, sur chaque participant, avec la cascade allumée : c'est
        l'union des deux premiers que la page peint, et un identifiant présent
        dans deux ensembles s'y afficherait deux fois, dans deux états
        contraires.
        """
        comp = jeu["competition"]
        comp.options = '{"validation_couleur": 1}'
        db.session.commit()
        for p in jeu["participants"]:
            for b in jeu["blocs"]:
                db.session.add(Success(participant_id=p.id, bloc_id=b.id))
        db.session.commit()
        invalider()

        for p in jeu["participants"]:
            e = blocs_du_grimpeur(comp, p)
            assert not (e["grimpes"] & e["credites"])
            assert not (e["grimpes"] & e["hors_circuit"])
            assert not (e["credites"] & e["hors_circuit"])

    def test_la_cascade_credite_sans_faire_grimper(self, jeu):
        """Un bloc crédité n'est JAMAIS dans `grimpes`.

        C'est ce qui permet à la fiche de le hachurer au lieu de le remplir —
        « pas grimpé mais compté ». Le confondre avec une réussite ferait
        compter à un parent des blocs que son enfant n'a pas faits.
        """
        comp = jeu["competition"]
        comp.options = '{"validation_couleur": 1}'
        db.session.commit()
        # Léa (U11) réussit le vert ; le jaune de son circuit est plus facile.
        lea, zj6, zj7 = jeu["participants"][0], jeu["blocs"][0], jeu["blocs"][1]
        reussite(lea, zj7)

        etats = blocs_du_grimpeur(comp, lea)
        assert zj7.id in etats["grimpes"]
        assert zj6.id in etats["credites"]
        assert zj6.id not in etats["grimpes"]


class TestLaFiche:

    def test_les_blocs_du_circuit_et_leur_etat(self, jeu):
        lea, zj6 = jeu["participants"][0], jeu["blocs"][0]
        reussite(lea, zj6)
        f = fiche(jeu["competition"], lea)

        assert f["participant"]["circuit"] == "U11"
        assert f["total"] == 2                      # ZJ6 et ZJ7
        assert f["grimpes"] == 1
        assert f["credites"] == 0
        etats = {b["tag"]: b["etat"] for g in f["groupes"] for b in g["blocs"]}
        assert etats == {"ZJ6": GRIMPE, "ZJ7": RESTE}

    def test_l_ordre_est_celui_du_classeur(self, jeu):
        """La difficulté d'abord, le numéro ensuite — l'ordre de la fiche
        PAPIER. Deux documents qui rangent les mêmes blocs autrement, c'est un
        document de plus à déchiffrer au lieu du même à jour."""
        f = fiche(jeu["competition"], jeu["participants"][0])
        assert [g["couleur"] for g in f["groupes"]] == ["Jaune", "Vert"]

    def test_le_numero_est_celui_ecrit_sur_le_mur(self, jeu):
        """« ZJ6 » porte « J6 » : c'est ce que le grimpeur lit sur l'étiquette,
        et ce que sa fiche papier affiche."""
        f = fiche(jeu["competition"], jeu["participants"][0])
        premier = f["groupes"][0]["blocs"][0]
        assert premier["tag"] == "ZJ6"
        assert premier["numero"] == "J6"
        assert premier["zone"] == "Z"

    def test_le_hors_circuit_n_apparait_pas(self, jeu):
        """Décision du 02/09 : la fiche s'arrête au tableau des blocs.

        L'anomalie reste traitable dans la console ; sur un écran public, un
        parent ne pourrait que s'en inquiéter.
        """
        lea, dv21 = jeu["participants"][0], jeu["blocs"][2]
        reussite(lea, dv21)
        f = fiche(jeu["competition"], lea)
        tags = {b["tag"] for g in f["groupes"] for b in g["blocs"]}
        assert "DV21" not in tags
        assert f["grimpes"] == 0

    def test_sans_categorie_la_fiche_se_rend_quand_meme(self, jeu):
        """Ce qui manque se DIT. Une fiche qui disparaît laisse chercher."""
        orphelin = Participant(competition_id=jeu["competition"].id,
                               nom="Sans", prenom="Categorie", dossard=99)
        db.session.add(orphelin)
        db.session.commit()
        f = fiche(jeu["competition"], orphelin)
        assert f["total"] == 0
        assert f["groupes"] == []
        assert "categorie" in f["manque"].lower()

    def test_circuit_inconnu_le_dit(self, jeu, competition):
        """Une catégorie dont le circuit n'a pas été importé."""
        p = Participant(competition_id=competition.id, nom="Perdu", prenom="Max",
                        categorie="U19 H", dossard=98)
        db.session.add(p)
        db.session.commit()
        f = fiche(competition, p)
        assert "U19" in f["manque"]

    def test_circuit_sans_bloc_le_dit(self, jeu, competition):
        """Un circuit connu mais vide — le cas que la vue « Circuits » signale."""
        db.session.add(Circuit(competition_id=competition.id, nom="U15"))
        db.session.commit()
        p = Participant(competition_id=competition.id, nom="Vide", prenom="Zoe",
                        categorie="U15 F", dossard=97)
        db.session.add(p)
        db.session.commit()
        f = fiche(competition, p)
        assert f["total"] == 0
        assert "Aucun bloc" in f["manque"]

    def test_les_compteurs_suivent_les_blocs_AFFICHES(self, jeu):
        """Un bloc réussi puis retiré du circuit ne doit pas gonfler le compteur.

        Sinon la fiche annonce « 2 grimpés » au-dessus d'un tableau qui n'en
        montre qu'un — et c'est le tableau qui a raison.
        """
        comp = jeu["competition"]
        lea, zj6, zj7 = jeu["participants"][0], jeu["blocs"][0], jeu["blocs"][1]
        reussite(lea, zj6)
        reussite(lea, zj7)
        assert fiche(comp, lea)["grimpes"] == 2

        BlocCircuit.query.filter_by(bloc_id=zj7.id).delete()
        db.session.commit()
        invalider()

        f = fiche(comp, lea)
        assert f["total"] == 1
        assert f["grimpes"] == 1


class TestLePlanServi:

    def test_il_porte_son_format(self, app):
        """Le numéro de format est le point de rendez-vous avec la page : sans
        lui, elle ne peut pas refuser un plan qu'elle ne sait pas dessiner."""
        assert plan_public()["format"] == FORMAT_PLAN

    def test_il_ne_depend_d_aucun_grimpeur(self, app):
        """Le mur est une constante. Le servir par grimpeur multiplierait les
        entrées de cache pour un dessin rigoureusement identique."""
        plan = plan_public()
        assert "sienne" not in str(plan)
        assert plan_public() == plan

    def test_chaque_mur_porte_ce_qu_il_faut_pour_le_dessiner(self, app):
        for mur in plan_public()["murs"]:
            assert mur["zone"]
            assert mur["profil"]
            assert "," in mur["d"]
            assert len(mur["etiquette"]) == 2
            assert mur["taille"] > 0

    def test_le_cadrage_deborde_la_vue(self, app):
        """La marge est sur le cadrage, jamais sur les coordonnées : sept murs
        d'Annonay touchent le bord du dessin."""
        plan = plan_public()
        x, y, largeur, hauteur = (float(v) for v in plan["cadrage"].split())
        assert x < 0 and y < 0
        assert largeur > plan["vue"][0] and hauteur > plan["vue"][1]

    def test_les_murs_sans_lettre_sont_ecartes(self, app):
        """Un mur sans zone ne peut être relié à aucun bloc : le montrer
        donnerait une forme sur laquelle on cliquerait sans effet."""
        assert all(m["zone"] for m in plan_public()["murs"])


class TestLaRoute:

    def test_elle_rend_la_fiche(self, client, jeu):
        lea = jeu["participants"][0]
        r = client.get(f"/api/public/grimpeur/{lea.id}")
        assert r.status_code == 200
        assert r.get_json()["participant"]["nom"] == "Dupont Lea"

    def test_grimpeur_inconnu(self, client, jeu):
        r = client.get("/api/public/grimpeur/99999")
        assert r.status_code == 404
        assert r.get_json()["success"] is False

    def test_un_grimpeur_d_une_autre_competition_est_invisible(self, client, jeu, app):
        """Sans cette garde, l'identifiant lirait les éditions passées, qui
        vivent dans la même base."""
        from climbcontest.models import Competition
        autre = Competition(nom="Edition passee")
        db.session.add(autre)
        db.session.flush()
        etranger = Participant(competition_id=autre.id, nom="Autre", prenom="Ana",
                               categorie="U11 F", dossard=1)
        db.session.add(etranger)
        db.session.commit()

        assert client.get(f"/api/public/grimpeur/{etranger.id}").status_code == 404

    def test_sans_competition_active(self, client, app):
        r = client.get("/api/public/grimpeur/1")
        assert r.status_code in (404, 409)
        assert r.get_json()["success"] is False

    def test_elle_ne_sert_pas_le_plan(self, client, jeu):
        """Le plan part avec la page, une fois. Le remettre dans chaque fiche
        le ferait voyager à chaque clic pour un dessin qui ne change pas."""
        r = client.get(f"/api/public/grimpeur/{jeu['participants'][0].id}")
        assert "murs" not in r.get_json()


class TestLeContratDuPlanNePourritPas:
    """Deux gardes qui ne verifient pas le code, mais l'ACCORD entre deux
    endroits qui doivent evoluer ensemble.

    C'est le meme principe que le controle des phrases de la spec 025 : une
    logique existant en deux exemplaires finit par diverger, et la divergence
    est silencieuse. Ici les deux exemplaires sont dans deux LANGAGES — le
    format annonce par Python, les formats acceptes par le JavaScript — et rien
    d'autre ne les confronterait.
    """

    # La forme exacte de `plan_public()`. ⚠️ Si tu modifies cette liste, tu dois
    # INCREMENTER `FORMAT_PLAN` : c'est ce numero qui permet a une page servie
    # depuis un cache de refuser un plan qu'elle ne sait pas dessiner, au lieu
    # de le dessiner de travers.
    CLES = {"format", "vue", "cadrage", "contour", "murs", "reperes"}
    CLES_MUR = {"zone", "profil", "d", "etiquette", "taille"}

    def test_la_forme_du_plan_est_celle_de_son_numero(self, app):
        plan = plan_public()
        assert set(plan) == self.CLES, (
            "la forme de plan_public() a change : incremente FORMAT_PLAN, "
            "sinon une page en cache dessinera un plan qu'elle croit connaitre")
        for mur in plan["murs"]:
            assert set(mur) == self.CLES_MUR, (
                "la forme d'un mur a change : incremente FORMAT_PLAN")
            # ⚠️ Les CLES ne suffisent pas. Deux changements realistes gardent
            # les memes clés et font dessiner un plan FAUX sans que rien ne
            # bronche : `d` passant a un chemin SVG (« M100,15 L115,15 »), et
            # `etiquette` passant d'une paire a un dictionnaire de deux clés —
            # dont `len()` vaut aussi 2. On verifie donc la FORME.
            assert re.fullmatch(r"-?[\d.]+,-?[\d.]+( -?[\d.]+,-?[\d.]+)+",
                                mur["d"]), (
                f"la geometrie n'est plus une liste de points : {mur['d']!r} — "
                "incremente FORMAT_PLAN")
            assert isinstance(mur["etiquette"], list), (
                "l'etiquette n'est plus une paire : incremente FORMAT_PLAN")
            assert len(mur["etiquette"]) == 2
            assert all(isinstance(v, (int, float)) for v in mur["etiquette"])
            assert isinstance(mur["taille"], (int, float))

    def test_la_page_sait_dessiner_ce_que_le_serveur_envoie(self, app):
        """Le serveur estampille, la page verifie l'estampille. Si les deux
        listes divergent, le mur disparait en silence — la page refuse
        poliment un plan parfaitement valide, et personne ne sait pourquoi."""
        import re
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "climbcontest/static/resultats/plan.js").read_text()
        bloc = re.search(r"FORMATS_RENDUS\s*=\s*\[(.*?)\]", source, re.S)
        assert bloc, "FORMATS_RENDUS introuvable dans plan.js"
        acceptes = re.findall(r'"([^"]+)"', bloc.group(1))
        assert FORMAT_PLAN in acceptes, (
            f"le serveur annonce « {FORMAT_PLAN} » et la page accepte "
            f"{acceptes} : le mur ne s'afficherait jamais")


class TestLeCompteurTientDansSonPan:
    """L'avancement par zone — spec 036, l'accord entre deux langages.

    La page pose « 1/4 » SOUS la lettre de la zone, sur une PASTILLE, a une
    place et des tailles calculees a partir de quatre ratios ecrits dans
    `plan.js`. Elle ne relit aucune geometrie : elle ne connait du pan que ce
    que le serveur lui en a dit — `etiquette` et `taille`.

    ⚠️ C'EST CE TEST QUI TIENT LA POSE B. La pastille se dimensionne sur la
    LETTRE, donc elle herite des bornes que `taille_lettre` a posees ; calibree
    sur son TEXTE, elle n'aurait aucune borne et sortirait du pan — c'est ce
    qui l'avait fait ecarter a la premiere maquette. Le socle est aussi ce qui
    a de plus gros a tenir : verifier le chiffre ne suffit plus, c'est le
    RECTANGLE qu'il faut mesurer.

    ⚠️ Personne d'autre ne confronte les deux cotes. Un ratio augmente « pour
    que ce soit plus lisible », un `taille_lettre` retouche, un plan d'usine
    redessine avec des pans plus bas : la pastille sort sous son pan, et rien
    ne le dit — ni un test JavaScript, qui n'a pas le plan, ni un test Python,
    qui n'a pas les ratios. Ce test a les deux.

    ⚠️ CE QU'IL NE COUVRE PAS : le plan que la console enregistre (spec 029).
    Il verifie le plan SERVI par ce test, donc celui d'usine. Le remede propre
    au cas general n'est pas une constante mieux choisie — il n'en existe
    aucune qui tienne dans un pan arbitrairement bas — c'est de faire calculer
    la place du compteur par le serveur, la ou la boite du pan est connue,
    comme `taille_lettre` calcule celle de la lettre. Ca change la forme de
    `plan_public()` et demande d'incrementer `FORMAT_PLAN` : un autre lot.
    """

    # La demi-hauteur d'une capitale grasse, en fraction de son corps, avec
    # `dominant-baseline: central`. Meme famille de constante que
    # `LARGEUR_CAPITALE` : elle sert a borner, pas a decrire.
    DEMI_HAUTEUR = 0.36
    # La largeur du pire chiffre tabulaire, en fraction de son corps.
    LARGEUR_CHIFFRE = 0.58

    @staticmethod
    def _ratio(source, nom):
        trouve = re.search(rf"(?:export )?const {nom} = ([\d.]+);", source)
        assert trouve, f"{nom} introuvable dans plan.js — le compteur n'est plus mesurable"
        return float(trouve.group(1))

    @staticmethod
    def _boite(d):
        points = [tuple(float(v) for v in p.split(",")) for p in d.split(" ")]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _source():
        from pathlib import Path

        return (Path(__file__).resolve().parent.parent
                / "climbcontest/static/resultats/plan.js").read_text()

    def test_la_lettre_et_sa_pastille_tiennent_dans_le_pan(self, app):
        """Trois bornes verticales, et elles se serrent toutes les trois.

        ⚠️ CE TEST A CHANGE DE FORME AVEC LA POSITION « E » (03/09). La lettre
        ne s'ecrit plus sur son centroide : elle MONTE de `LETTRE_MONTEE`, pour
        faire la place que la pastille n'avait pas en dessous. Trois choses
        peuvent donc sortir du pan au lieu d'une, et la troisieme est neuve :

          1. le HALO de la lettre, par le haut -- personne ne le surveillait,
             et c'est desormais lui le plus haut ;
          2. la pastille, par le bas ;
          3. la pastille contre le halo : ils se chevauchaient de 0,104 x taille
             avant ce lot, et c'est exactement ce qu'Adrien a vu (« la c'est
             trop proche »).

        ⚠️ On mesure le HALO et non le glyphe : le halo est ce qui se voit, et
        c'est lui qui touchait la pastille.
        """
        source = self._source()
        echelle = self._ratio(source, "COMPTE_ECHELLE")
        descente = self._ratio(source, "COMPTE_DESCENTE")
        hauteur = self._ratio(source, "PASTILLE_HAUTEUR")
        montee = self._ratio(source, "LETTRE_MONTEE")
        # `HALO` est l'EPAISSEUR du trait, centre sur le contour du glyphe : il
        # deborde donc de sa moitie.
        halo = self.DEMI_HAUTEUR + self._ratio(source, "HALO") / 2

        for mur in plan_public()["murs"]:
            _, y_haut, _, y_bas = self._boite(mur["d"])
            taille = mur["taille"]
            y = mur["etiquette"][1]
            demi = taille * echelle * hauteur / 2
            centre = y + taille * descente
            lettre = y - taille * montee

            assert lettre - taille * halo >= y_haut, (
                f"zone {mur['zone']} : le halo de la lettre monte a "
                f"{lettre - taille * halo:.2f} pour un pan qui commence a "
                f"{y_haut:.2f}. Baisse LETTRE_MONTEE dans plan.js.")

            assert centre + demi <= y_bas, (
                f"zone {mur['zone']} : la pastille descend a "
                f"{centre + demi:.2f} pour un pan qui s'arrete a {y_bas:.2f}. "
                f"Baisse COMPTE_DESCENTE, COMPTE_ECHELLE ou PASTILLE_HAUTEUR "
                f"dans plan.js, ou fais calculer la place par le serveur.")

            assert centre - demi >= lettre + taille * halo, (
                f"zone {mur['zone']} : la pastille touche le halo de la lettre "
                f"-- c'est le defaut qu'on vient de corriger. Augmente "
                f"LETTRE_MONTEE ou COMPTE_DESCENTE dans plan.js.")

    def test_la_pastille_ne_sort_pas_sur_les_cotes(self, app):
        """Meme garde en largeur — et c'est celle qui avait cede.

        La pastille fait `PASTILLE_LARGEUR x taille` de large, quel que soit
        son libelle. `taille_lettre` a deja borne `taille` par la boite du pan,
        et c'est ce lien-la que ce test verifie sur le releve reel.

        ⚠️ IL S'EST RESSERRE LE 03/09 : la pastille est passee de 1,0 a 1,6 fois
        la lettre pour porter la jauge, soit 14,4 unites dans un pan de 15. Il
        reste 0,3 unite de chaque cote -- la pastille croise donc le cadre
        « terminee » et lui passe devant, ce qui est assume. Ce qu'elle ne doit
        jamais faire, c'est sortir du pan : au-dela, elle irait chez la voisine.
        """
        source = self._source()
        largeur = self._ratio(source, "PASTILLE_LARGEUR")

        for mur in plan_public()["murs"]:
            x_gauche, _, x_droite, _ = self._boite(mur["d"])
            demi = mur["taille"] * largeur / 2
            x = mur["etiquette"][0]
            assert x - demi >= x_gauche and x + demi <= x_droite, (
                f"zone {mur['zone']} : la pastille deborde du pan en largeur")

    def test_le_chiffre_tient_dans_la_pastille(self, app):
        """Le libelle courant « 1/4 » est le PIRE cas : les plus longs

        retrecissent (`tailleDuCompte`). Si trois chiffres au pire glyphe ne
        tiennent pas dans le socle, le fond censes les porter ne les porte pas.
        """
        source = self._source()
        echelle = self._ratio(source, "COMPTE_ECHELLE")
        largeur = self._ratio(source, "PASTILLE_LARGEUR")

        for mur in plan_public()["murs"]:
            taille = mur["taille"]
            texte = 3 * self.LARGEUR_CHIFFRE * taille * echelle
            assert texte <= taille * largeur, (
                f"zone {mur['zone']} : « 1/4 » fait {texte:.2f} de large pour "
                f"une pastille de {taille * largeur:.2f}")


class TestCeQuiPartDansLaPage:
    """Le plan est EMBARQUE dans le HTML : ce qui suit ne se verifie donc pas
    dans un navigateur, et rien ne le couvrait."""

    def test_la_page_porte_le_plan(self, client, jeu):
        page = client.get("/").data.decode()
        assert 'id="plan-du-mur"' in page
        debut = page.index('id="plan-du-mur">') + len('id="plan-du-mur">')
        plan = json.loads(page[debut:page.index("</script>", debut)])
        assert plan["format"] == FORMAT_PLAN
        assert plan["murs"]

    def test_un_libelle_hostile_ne_sort_pas_du_bloc(self, client, jeu, app):
        """⚠️ `json.dumps` n'echappe pas « < ».

        Depuis la spec 029, le plan est de la donnee SAISIE depuis la console :
        un `</script>` dans un libelle de repere fermerait le bloc JSON, et la
        suite deviendrait du balisage vivant — sur une page publique, servie a
        tous les spectateurs et projetee dans la salle. Le depot est public :
        c'est une escalade organisateur vers public.
        """
        from climbcontest import plan_du_mur
        plan_du_mur.ecrire({
            "vue": [120, 150], "contour": None,
            "murs": [{"zone": "Z", "profil": "vertical",
                      "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}],
            "reperes": [{"texte": "</script><svg onload=x>", "point": [5, 5]}],
        })
        page = client.get("/").data.decode()
        # Le bloc JSON ne doit se fermer qu'UNE fois, et pas dans la charge.
        avant = page[:page.index('id="plan-du-mur">')]
        apres = page[page.index('id="plan-du-mur">'):]
        assert "</script" not in apres[: apres.index("</script>")]
        assert "\\u003c" in apres[: apres.index("</script>")]
        assert "<svg onload" not in apres[: apres.index("</script>")]


class TestUnSeulAccesseur:
    """`blocs_du_grimpeur` doit etre definie UNE FOIS dans le module.

    ⚠️ La spec 025 ajoute une fonction du meme nom au meme fichier, a un autre
    endroit. Git fusionne alors SANS CONFLIT, le module la definit deux fois, et
    la seconde ecrase la premiere en silence : c'est l'ordre dans le fichier qui
    choisit laquelle des deux resolutions de la cascade s'applique a la fiche du
    grimpeur. Ce test transforme ce silence en echec rouge.
    """

    def test_definie_une_seule_fois(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent.parent
                  / "climbcontest/classement_service.py").read_text()
        assert source.count("def blocs_du_grimpeur(") == 1, (
            "deux definitions de blocs_du_grimpeur : la seconde ecrase la "
            "premiere en silence. Fusionne-les en une seule.")
