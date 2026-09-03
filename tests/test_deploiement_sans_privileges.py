"""Le bouton « Installer » ne peut pas s'élever, et ne doit plus essayer.

Ces tests sont nés d'un défaut livré en v0.17.0 et resté invisible jusqu'au
premier vrai clic, le 2026-09-03 : la console répondait « Le service de
déploiement n'a pas pu être démarré », **à tous les coups**.

L'appel était `sudo -n systemctl start --no-block climbcontest-deploy.service`.
La règle sudoers l'autorisait mot pour mot. Elle ne pouvait rien :
`climbcontest.service` tourne avec `NoNewPrivileges=true`, qui interdit à ses
processus de gagner des privilèges par un binaire **setuid** — et `sudo` en est
un. Vérifié sur la VM :

    $ systemd-run --uid=climbcontest -p NoNewPrivileges=yes /usr/bin/sudo -n -l
    sudo: The "no new privileges" flag is set, which prevents sudo
          from running as root.

Les tests de `test_maj_serveur.py` remplaçaient `subprocess.run` par un leurre.
Ils prouvaient qu'on **appelait** sudo ; jamais que l'appel pouvait aboutir. Un
test qui simule la seule chose qui casse ne surveille rien.

Ce que ces tests-ci vérifient tient dans le contrat entre trois fichiers que
personne ne lit ensemble : l'unité de l'application, celle du guetteur, et le
code qui écrit la demande.
"""
import re
from pathlib import Path


from climbcontest import maj

RACINE = Path(__file__).resolve().parent.parent
DEPLOIEMENT = RACINE / "deployment"
APPLICATION = DEPLOIEMENT / "climbcontest.service"
GUETTEUR = DEPLOIEMENT / "climbcontest-deploy.path"
AGENT = DEPLOIEMENT / "climbcontest-deploy.service"
INSTALL = DEPLOIEMENT / "install.sh"


def directives(unite: Path, cle: str) -> list[str]:
    """Toutes les valeurs d'une directive systemd, commentaires exclus."""
    valeurs = []
    for ligne in unite.read_text(encoding="utf-8").splitlines():
        nue = ligne.strip()
        if nue.startswith("#") or "=" not in nue:
            continue
        nom, _, valeur = nue.partition("=")
        if nom.strip() == cle:
            valeurs.append(valeur.strip())
    return valeurs


class TestLApplicationNeSEleveJamais:
    """Le durcissement est la contrainte, pas une option qu'on contourne."""

    def test_le_service_applicatif_interdit_toute_elevation(self):
        assert directives(APPLICATION, "NoNewPrivileges") == ["true"], (
            "Si ce durcissement disparaît, ce n'est pas une ligne de config qui "
            "change : c'est le service exposé au wifi de la salle qui redevient "
            "capable de s'élever. Le bouton se répare par climbcontest-deploy"
            ".path, jamais en retirant ceci."
        )

    def test_aucun_module_de_l_application_ne_lance_de_processus(self):
        """`sudo` ne peut pas aboutir ici. Rien ne doit plus le tenter.

        On ne cherche pas le mot « sudo » — il vit légitimement dans les
        commentaires qui racontent cette panne. On interdit le MOYEN : lancer
        un processus. Sous `NoNewPrivileges=true`, aucun binaire setuid ne
        servira jamais à rien depuis ce code.
        """
        interdits = re.compile(
            r"^\s*(?:import\s+subprocess|from\s+subprocess\s+import)"
            r"|os\.system\(|os\.popen\(|os\.exec[lv]",
            re.M)
        fautifs = [
            str(f.relative_to(RACINE))
            for f in sorted((RACINE / "climbcontest").rglob("*.py"))
            if interdits.search(f.read_text(encoding="utf-8"))
        ]
        assert not fautifs, (
            f"{fautifs} lance un processus. L'application tourne avec "
            "NoNewPrivileges=true : elle ne peut pas s'élever, et un appel qui "
            "en dépend échouera en production sans jamais échouer en test. "
            "Passer par une unité systemd déclenchée par un fichier."
        )


class TestLeGuetteurRemplaceSudo:
    """Ce que l'application ne peut pas faire, systemd le fait pour elle."""

    def test_le_chemin_ecrit_est_celui_qui_est_surveille(self, monkeypatch):
        """Le contrat tient en une égalité, et il n'était vérifié nulle part.

        On ne recopie pas le chemin : on demande à l'application où elle écrit,
        pour que déplacer le fichier casse ce test au lieu de casser le bouton.
        """
        surveilles = directives(GUETTEUR, "PathChanged")
        assert len(surveilles) == 1
        monkeypatch.setenv("CLIMBCONTEST_BASE", "/opt/climbcontest")
        attendu = str(maj._demande())
        assert surveilles[0] == attendu, (
            f"Le guetteur surveille {surveilles[0]}, l'application écrit "
            f"{attendu}. Deux fichiers différents : le bouton ne déclenche rien "
            "et ne dit rien."
        )

    def test_le_guetteur_demarre_bien_l_agent(self):
        assert directives(GUETTEUR, "Unit") == ["climbcontest-deploy.service"]
        assert AGENT.exists()

    def test_il_ecoute_les_MODIFICATIONS_et_pas_l_existence(self):
        """`PathExists` casserait le bouton de deux façons distinctes.

        Le second clic réécrit le même fichier : sans transition, `PathExists`
        resterait muet et le bouton ne marcherait qu'une fois. Et une demande
        qui traîne relancerait l'agent **au démarrage de la machine** — une
        installation automatique le matin d'une compétition, exactement ce que
        la spec 031 a supprimé.
        """
        assert not directives(GUETTEUR, "PathExists")
        assert directives(GUETTEUR, "PathChanged")

    def test_la_demande_vit_dans_le_seul_dossier_accessible_en_ecriture(self):
        """Sous `ProtectSystem=strict`, tout le reste de /opt est en lecture."""
        autorises = directives(APPLICATION, "ReadWritePaths")
        assert autorises, "sans ReadWritePaths, l'application n'écrit nulle part"
        cible = directives(GUETTEUR, "PathChanged")[0]
        assert any(cible.startswith(f"{chemin.rstrip('/')}/") for chemin in autorises), (
            f"{cible} n'est sous aucun de {autorises} : l'écriture serait "
            "refusée par systemd, et le bouton retomberait en panne autrement."
        )


class TestCeQueLaVmDoitAvoir:
    """Une unité qui n'est ni installée ni activée ne guette rien."""

    def test_install_pose_et_active_le_guetteur(self):
        texte = INSTALL.read_text(encoding="utf-8")
        assert "climbcontest-deploy.path" in texte
        assert re.search(r"systemctl enable[^\n]*climbcontest-deploy\.path", texte), (
            "installée mais pas activée, elle ne surveille rien"
        )

    def test_l_autorisation_sudo_morte_a_ete_retiree(self):
        """La laisser ferait croire que ce chemin existe encore."""
        ligne = next(l for l in INSTALL.read_text(encoding="utf-8").splitlines()
                     if "NOPASSWD" in l and not l.strip().startswith("#"))
        assert "climbcontest-deploy" not in ligne, (
            "sudo ne peut pas démarrer l'agent depuis l'application : cette "
            "autorisation est sans effet, et sa présence relancerait l'enquête."
        )
        assert "systemctl restart climbcontest" in ligne, (
            "l'agent de déploiement, lui, en a toujours besoin — il n'est pas durci"
        )
