"""
Koda, le tuteur incarné — ce que l'animation n'a pas le droit de faire.

Compétence visée : C17 (épreuve E4) — application web
Compétences concernées : C13 (E3) — accessibilité ; C21 (E5)

Le personnage accompagne les messages du tuteur ; il ne les remplace jamais.
Ces tests fixent cette règle et les protections d'accessibilité, qu'aucune
relecture ne garantit durablement.
"""

import json
import re
from pathlib import Path

import pytest
from django.urls import reverse

SCRIPT = Path("static/js/koda.js")
FEUILLE = Path("static/css/tailwind.css")
DESCRIPTEUR = Path("static/img/koda/planches/planches.json")
PANNEAU = Path("templates/components/tuteur.html")


FICHIER_REFERENTIEL = "apps/referentiel/donnees/eduai-2026.json"


@pytest.fixture
def referentiel():
    from io import StringIO

    from django.core.management import call_command

    from apps.referentiel.models import Competence

    call_command("importer_referentiel", FICHIER_REFERENTIEL, "--activer",
                 stdout=StringIO())
    return Competence.objects.get(code="collections")


@pytest.fixture
def apprenante(django_user_model):
    return django_user_model.objects.create_user(
        username="apprenante", email="apprenante@exemple.test",
        password="mot-de-passe-d-essai-2026")


@pytest.mark.django_db
def test_les_messages_du_tuteur_restent_dans_le_html_rendu(client, apprenante):
    """
    Aucune information n'est portée par la seule animation.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Un personnage qui s'agite ne dit rien à qui ne le voit pas — ni à un
    lecteur d'écran, ni à quelqu'un qui a coupé les animations, ni à qui
    regarde ailleurs. Le texte doit donc rester présent quoi qu'il arrive.
    """
    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()

    # Les libellés destinés à JavaScript traversent `escapejs`, qui rend une
    # apostrophe sous la forme `\u0027`. Le texte est bien là, sous une écriture
    # que ce test doit savoir lire : chercher l'apostrophe brute reviendrait à
    # exiger une insertion non échappée, c'est-à-dire le défaut du 02/09/2026.
    page = page.replace("\\u0027", "'")

    for message in ("Le tuteur réfléchit", "La réponse n'a pas pu être obtenue"):
        assert message in page, (
            "« %s » doit rester dans le HTML : Koda ne le porte pas à sa place"
            % message
        )


@pytest.mark.django_db
def test_le_reglage_du_profil_fige_le_personnage(client, apprenante):
    """
    Décocher l'animation dans le profil fige Koda, indépendamment du système.

    Compétence visée : C17 (épreuve E4), C13 (E3)
    """
    client.force_login(apprenante)
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()
    assert 'data-animation="desactivee"' not in page

    apprenante.animation_koda = False
    apprenante.save()
    page = client.get(reverse("tracker:dashboard"), secure=True).content.decode()
    assert 'data-animation="desactivee"' in page, (
        "le réglage du profil doit atteindre le gabarit"
    )


def test_le_mouvement_reduit_est_respecte_par_la_feuille_et_par_le_script():
    """
    Les deux protections contre le mouvement sont en place.

    Compétence visée : C13 (épreuve E3) — accessibilité

    La feuille de style fige le personnage même si le script tarde ou échoue ;
    le script cesse en plus de parcourir la planche, pour ne pas consommer une
    batterie à afficher une image qui ne change pas. L'une des deux suffirait
    en régime normal — c'est bien pour cela qu'il en faut deux.
    """
    feuille = FEUILLE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    assert "prefers-reduced-motion:reduce" in feuille.replace(" ", ""), (
        "la feuille compilée doit contenir la règle de mouvement réduit"
    )
    assert "prefers-reduced-motion: reduce" in script
    assert "document.hidden" in script, (
        "une boucle ne doit pas tourner dans un onglet en arrière-plan"
    )
    assert "offsetParent === null" in script, (
        "une boucle ne doit pas tourner derrière un panneau replié"
    )


def test_la_boucle_de_repos_est_muette_pour_un_lecteur_d_ecran():
    """
    Le repos est décoratif ; seuls les états qui signifient quelque chose parlent.

    Compétence visée : C13 (épreuve E3) — accessibilité

    Un lecteur d'écran ne doit pas annoncer « Koda respire » toutes les deux
    secondes. L'alternative textuelle n'est posée que pour les états déclarés.
    """
    panneau = PANNEAU.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'data-etat-initial="repos"' in panneau
    assert 'aria-hidden="true"' in panneau
    assert "data-alt-parle" in panneau, "l'état « parle » doit être annoncé"
    assert 'setAttribute("aria-hidden", "true")' in script, (
        "un état sans alternative textuelle doit redevenir muet"
    )


def test_aucun_etat_ne_designe_une_image_absente_de_la_planche():
    """
    Les indices de la table d'états tiennent dans la planche.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Une coquille dans un indice n'échoue pas : elle affiche une case vide ou la
    mauvaise expression, et personne ne rapproche cela d'un chiffre. Ce test
    remplace cette relecture.
    """
    script = SCRIPT.read_text(encoding="utf-8")
    planches = json.loads(DESCRIPTEUR.read_text(encoding="utf-8"))

    for jeu, planche in (("grosPlan", "gros_plan"),):
        debut = script.index("JEUX.%s = {" % jeu)
        table = script[debut:script.index("};", debut)]
        indices = [int(n) for n in re.findall(r"\b(\d+)\b", re.sub(
            r"(cadence|reposMin|reposMax)\s*:\s*\d+", "", table))]
        disponibles = planches[planche]["images"]

        assert indices, "la table d'états de %s doit être lisible" % jeu
        assert max(indices) < disponibles, (
            "%s désigne l'image %d, la planche en compte %d"
            % (jeu, max(indices), disponibles)
        )


def test_la_planche_est_servie_en_une_seule_requete():
    """
    Une image par famille de cadrage, pas une par frame.

    Compétence visée : C13 (épreuve E3) — poids des ressources
    """
    # Les commentaires du gabarit citent forcément le chemin de la planche :
    # un test qui les compte interdit d'expliquer ce que fait le code.
    panneau = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "",
                     PANNEAU.read_text(encoding="utf-8"), flags=re.S)
    planches = json.loads(DESCRIPTEUR.read_text(encoding="utf-8"))

    # Ce qui compte est le nombre de requêtes, pas le nombre de balises : deux
    # Koda à l'écran — celui de la poignée et celui du panneau — désignent la
    # même image, et le navigateur ne la télécharge qu'une fois.
    citees = set(re.findall(r"img/koda/planches/[\w.-]+", panneau))
    assert len(citees) == 1, (
        "le panneau ne doit charger qu'une planche, il en cite %s" % sorted(citees)
    )
    poids = Path("static", planches["gros_plan"]["fichier"]).stat().st_size
    assert poids < 80 * 1024, (
        "la planche du panneau est servie sur toutes les pages : %d Kio"
        % (poids // 1024)
    )


# --- Ce que Koda a le droit de dire ---------------------------------------


SALUTATION = Path("apps/chat/salutation.py")


@pytest.mark.django_db
def test_koda_appelle_l_apprenant_par_son_pseudonyme(apprenante):
    """
    Le pseudonyme figure dans la salutation.

    Compétence visée : C17 (épreuve E4)
    """
    from apps.chat.salutation import saluer

    assert "apprenante" in saluer(apprenante)["phrase"]


@pytest.mark.django_db
def test_koda_n_invente_aucune_seance_a_qui_n_a_rien_fait(apprenante):
    """
    Un compte sans activité reçoit une salutation qui n'affirme rien.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    C'est ici que le faux s'introduit le plus facilement : une mascotte
    chaleureuse appelle des phrases qui « sonnent bien » — « content de te
    revoir », « tu progresses ». Adressées à quelqu'un qui vient de s'inscrire,
    ce sont des affirmations fausses. Le projet a retiré sept foyers de données
    fabriquées ; celui-ci n'en sera pas le huitième.
    """
    from apps.chat.salutation import saluer

    salutation = saluer(apprenante)

    assert "revoir" not in salutation["phrase"].lower(), (
        "on ne revoit pas quelqu'un qu'on n'a jamais vu"
    )
    for interdit in ("jours", "série", "progress", "bravo"):
        assert interdit not in salutation["detail"].lower(), (
            "« %s » affirme quelque chose que la base ne dit pas" % interdit
        )


@pytest.mark.django_db
def test_koda_nomme_la_notion_que_la_base_connait(apprenante, referentiel):
    """
    Le détail de la salutation vient d'une erreur réellement enregistrée.

    Compétence visée : C17 (épreuve E4), C20 (E5)
    """
    from apps.agents.agent_watcher import UserMistake
    from apps.chat.salutation import saluer

    UserMistake.objects.create(
        user=apprenante, topic="Manipuler les listes", mistake_type="quiz",
        question="?", user_answer="faux", correct_answer="vrai",
        competence=referentiel,
    )

    assert referentiel.intitule in saluer(apprenante)["detail"]


def test_koda_n_emploie_pas_un_compteur_que_personne_ne_tient():
    """
    `current_streak` est interdit à la salutation.

    Compétence visée : C21 (épreuve E5)

    Le champ existe et il est lu ailleurs pour calculer un bonus d'expérience,
    mais **rien ne l'écrit jamais** : il vaut zéro pour tout le monde
    (réserve 19). Une phrase du genre « trois jours d'affilée ! » serait donc
    fausse pour chaque apprenant, tout en paraissant la chose la plus naturelle
    à dire.
    """
    source = SALUTATION.read_text(encoding="utf-8")
    code = "\n".join(ligne for ligne in source.split("\n")
                     if not ligne.strip().startswith("#"))
    corps = code.split('"""', 2)[-1]

    assert "current_streak" not in corps, (
        "un compteur que rien ne met à jour ne peut pas être annoncé"
    )


def test_la_salutation_ne_depense_aucune_generation():
    """
    Dire bonjour ne consomme pas le quota du jour.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Quinze générations par jour et par apprenant (décision 030). En dépenser
    une pour une phrase d'accueil serait absurde — et rendrait l'accueil
    dépendant d'un service distant.
    """
    source = SALUTATION.read_text(encoding="utf-8")

    for interdit in ("orchestrator", "get_orchestrator", "consommer", "generate"):
        assert interdit not in source, (
            "la salutation doit être assemblée localement, pas engendrée"
        )


# --- Ce que Koda dit à la fin d'une partie --------------------------------


JEU = Path("apps/quiz/templates/quiz/multiplayer_game.html")


def test_les_deux_issues_ont_plusieurs_phrases_traduisibles():
    """
    Ce que Koda dit varie, et passe par les catalogues.

    Compétence visée : C17 (épreuve E4)

    Une seule phrase par issue serait vue deux fois et cesserait d'amuser.
    Un texte écrit en dur dans le script ne serait jamais traduit.
    """
    gabarit = JEU.read_text(encoding="utf-8")

    for prefixe, issue in (("t_gagne", "vainqueur"), ("t_perd", "perdant")):
        declarees = re.findall(r"\{%\s*trans\s+\"[^\"]+\"\s+as\s+" + prefixe + r"\d+\s*%\}",
                               gabarit)
        assert len(declarees) >= 3, (
            "il faut plusieurs phrases pour le %s, il y en a %d"
            % (issue, len(declarees))
        )


def test_koda_ne_reproche_rien_au_perdant():
    """
    Les phrases de défaite portent sur le pari de Koda, pas sur l'apprenant.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    La séquence employée montre un personnage qui crie, poings serrés. Servie
    seule, elle dit au perdant que le tuteur est en colère contre lui. C'est la
    phrase qui décide contre qui — et aucune ne doit désigner sa performance.
    """
    gabarit = JEU.read_text(encoding="utf-8")
    phrases = re.findall(r"\{%\s*trans\s+\"([^\"]+)\"\s+as\s+t_perd\d+\s*%\}", gabarit)

    assert phrases, "les phrases de défaite doivent être déclarées"
    for phrase in phrases:
        minuscule = phrase.lower()
        for reproche in ("nul", "mauvais", "raté", "déçu", "révise", "concentre"):
            assert reproche not in minuscule, (
                "« %s » reproche quelque chose au perdant" % phrase
            )


def test_le_koda_de_fin_de_partie_est_decoratif():
    """
    L'issue de la partie est lisible sans l'image.

    Compétence visée : C13 (épreuve E3) — accessibilité
    """
    gabarit = JEU.read_text(encoding="utf-8")
    fin = gabarit[gabarit.index("function showFinalResults"):]

    assert 'aria-hidden="true"' in fin, "le personnage de fin est décoratif"
    assert "${mot}" in fin, "la phrase doit être du texte, pas seulement une image"
    assert "construirePodium" in fin, "le classement reste affiché"


def test_les_boucles_de_fin_tiennent_dans_leurs_planches():
    """
    Les deux séquences de fin sont parcourues jusqu'à leur dernière image, pas au-delà.

    Compétence visée : C17 (épreuve E4), C21 (E5)
    """
    script = SCRIPT.read_text(encoding="utf-8")
    planches = json.loads(DESCRIPTEUR.read_text(encoding="utf-8"))

    borne = re.search(r"for \(var i = 0; i < (\d+); i \+= 1\)", script)
    assert borne, "la boucle de remplissage doit être lisible"
    bornes = int(borne.group(1))

    for planche in ("joie", "bouderie"):
        assert planches[planche]["images"] == bornes, (
            "la planche %s compte %d images, la boucle en parcourt %d"
            % (planche, planches[planche]["images"], bornes)
        )


def test_aucune_constante_du_script_n_est_employee_sans_etre_declaree():
    """
    Toute constante employée par `koda.js` y est déclarée.

    Compétence visée : C17 (épreuve E4), C21 (E5)

    Trois constantes ont disparu du script en retirant un bloc voisin, et leurs
    emplois sont restés. `Koda.brancher()` levait alors
    `ETATS_EVEILLES is not defined` **au chargement de chaque page** : plus
    aucun Koda n'était animé — ni la parole, ni l'assoupissement. Rien ne le
    signalait, parce qu'une planche de sprites qui ne bouge pas affiche
    simplement sa première image. Le personnage avait l'air en place.

    `node --check` ne voit pas ce défaut : la syntaxe est valide. Seule
    l'exécution le révèle, et ce test la remplace par une lecture.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    code = "\n".join(ligne for ligne in source.split("\n")
                     if not ligne.strip().startswith(("*", "/*", "//")))

    declarees = set(re.findall(r"var ([A-Z][A-Z_]+)\s*=", code))
    employees = set(re.findall(r"\b([A-Z][A-Z_]{3,})\b", code))
    # Les objets globaux du navigateur ne sont pas des constantes du script.
    employees -= {"JSON", "Math", "Array"}

    manquantes = sorted(employees - declarees)
    assert manquantes == [], (
        "employées sans être déclarées, le script lèvera au chargement : %s"
        % manquantes
    )


# --- Les réactions du quiz solo et de l'exercice --------------------------


SOLO = Path("apps/quiz/templates/quiz/quiz_start.html")
EXERCICE = Path("apps/exercises/templates/exercises/exercise_detail.html")


def test_le_quiz_solo_n_annonce_plus_son_resultat_par_une_boite_native():
    """
    Le résultat s'affiche dans la page, pas dans un `alert()`.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Une boîte de dialogue native ne se met pas en forme, échappe aux catalogues
    de traduction, et disparaît au clic : l'apprenant n'avait plus rien sous
    les yeux au moment où la page se rechargeait.

    L'écran de fin a été refait le 02/09/2026 : il n'est plus une fenêtre
    modale mais une section qui remplace le quiz dans la page. Les assertions
    qui décrivaient la fenêtre — `role="dialog"`, `aria-modal` — ont donc été
    retirées : elles décrivaient une conception, non une garantie. Ce qui reste
    ici est ce qui vaut quelle que soit la forme retenue.
    """
    gabarit = SOLO.read_text(encoding="utf-8")
    fin = gabarit[gabarit.index("function showResults"):]

    assert "alert(" not in fin, "le résultat ne doit plus passer par une boîte native"


def test_le_clavier_suit_le_resultat_affiche():
    """
    Le focus est amené au titre du résultat.

    Compétence visée : C13 (épreuve E3) — accessibilité

    L'écran de fin remplace le quiz DANS la page. Sans déplacement du focus,
    qui navigue au clavier ou par lecteur d'écran reste posé sur un contenu qui
    n'existe plus, et rien n'annonce le résultat. Ce n'est plus une fenêtre :
    on n'y piège pas le focus, on l'y amène.
    """
    gabarit = SOLO.read_text(encoding="utf-8")

    assert 'id="titre-resultats" tabindex="-1"' in gabarit, (
        "le titre du résultat doit pouvoir recevoir le focus"
    )
    fin = gabarit[gabarit.index("function showResults"):]
    assert ".focus()" in fin, "le clavier doit être amené au résultat"


def test_le_score_reste_du_texte_dans_l_ecran_de_fin_solo():
    """
    Koda accompagne le résultat, il ne le porte pas.

    Compétence visée : C13 (épreuve E3) — accessibilité
    """
    gabarit = SOLO.read_text(encoding="utf-8")
    fin = gabarit[gabarit.index("function showResults"):]

    assert "${score} / ${questions.length}" in fin, "le score doit être écrit"
    assert "${palier}" in fin, "le commentaire de palier doit être écrit"
    assert 'aria-hidden="true"' in fin, "le personnage est décoratif"


def test_le_resultat_part_au_serveur_avant_tout_affichage():
    """
    L'enregistrement précède l'écran de fin, et lui survit.

    Compétence visée : C20 (épreuve E5), C21 (E5)

    La chaîne d'enregistrement du quiz solo était écrite, joignable, et rien ne
    l'appelait (incident 010). Refaire l'écran de fin est exactement l'occasion
    de la débrancher à nouveau sans s'en apercevoir — et la réécriture du
    02/09/2026 avait en effet inversé l'ordre : l'affichage partait d'abord.

    Ce test lit l'ordre dans le code appelant, pas dans `showResults` : c'est
    là que la décision se prend.
    """
    gabarit = SOLO.read_text(encoding="utf-8")

    assert "quiz:submit" in gabarit, "le résultat doit être envoyé au serveur"
    assert "keepalive: true" in gabarit, (
        "la requête doit survivre à une navigation"
    )
    assert gabarit.index("quiz:submit") < gabarit.index("showResults(score"), (
        "l'envoi doit précéder l'affichage"
    )


def test_l_exercice_reussi_fete_sans_interrompre():
    """
    Koda félicite en passant, et ne demande rien à personne.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Une fenêtre modale sortirait l'apprenant de ce qu'il vient de faire.
    `pointer-events-none` garantit que le personnage n'intercepte aucun clic.
    """
    gabarit = EXERCICE.read_text(encoding="utf-8")

    assert "feterLaReussite();" in gabarit, "la réussite doit déclencher la fête"
    fete = gabarit[gabarit.index("function feterLaReussite"):]
    assert "pointer-events-none" in fete, (
        "le personnage ne doit intercepter aucun clic"
    )
    assert 'aria-hidden="true"' in fete
    assert "boite.remove()" in fete, "il passe, il ne s'installe pas"


# --- Koda est-il réellement branché là où on le pilote ? ------------------

COURS = Path("apps/courses/templates/courses/page_de_cours.html")


def test_la_page_de_cours_charge_l_animateur_qu_elle_pilote():
    """
    Piloter les états de Koda suppose son animateur et un élément à animer.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C21 (E5)

    La page appelait `Koda.etat('reflechit')` puis `Koda.etat('parle')` alors
    que ni `koda.js` ni aucun élément `data-koda` n'existaient ici : `koda.js`
    n'était chargé que par le panneau flottant, que cette page écarte pour ne
    pas afficher deux Koda. `window.Koda` était donc indéfini et chaque appel
    tombait dans le vide — écrit, atteignable, jamais exécuté.
    """
    gabarit = COURS.read_text(encoding="utf-8")

    if "Koda.etat(" not in gabarit:
        pytest.skip("cette page ne pilote plus Koda")

    assert "js/koda.js" in gabarit, "l'animateur doit être chargé par la page"
    assert "data-koda" in gabarit, "il faut un élément à animer"
    for attribut in ("data-colonnes", "data-largeur", "data-hauteur"):
        assert attribut in gabarit, f"{attribut} manque à l'élément animé"


def test_la_poignee_de_koda_se_deplace_et_retient_sa_place():
    """
    Koda peut être posé ailleurs, à la souris comme au clavier.

    Compétence visée : C17 (épreuve E4)
    Compétence concernée : C13 (E3) — accessibilité

    Koda se tient en bas à droite, là où les pages posent leur action
    principale : sur le quiz solo, il masquait « Voir mes résultats ». Réserver
    un coin sur chaque page serait une règle qu'on oublierait à la page
    suivante ; c'est donc le personnage qui se déplace.

    Trois garanties, et chacune répare un défaut prévisible :
    le clavier, sans quoi la fonction n'existerait qu'à la souris ;
    la position retenue, sans quoi il faudrait le déplacer à chaque page ;
    le re-bornage à la fenêtre, sans quoi un écran plus petit l'emporterait
    hors champ, irrattrapable.
    """
    composant = PANNEAU.read_text(encoding="utf-8")

    assert "tuteur-position-poignee" in composant, "la position doit être retenue"
    assert "ArrowLeft" in composant and "ArrowDown" in composant, (
        "les flèches du clavier doivent déplacer la poignée"
    )
    assert "window.addEventListener('resize', replacerLaPoignee)" in composant, (
        "la poignée doit être ramenée dans la fenêtre quand celle-ci change"
    )
    assert "Math.max(0, Math.min(x, window.innerWidth" in composant, (
        "la position doit être bornée à la fenêtre"
    )
    # Un déplacement ne doit pas ouvrir le panneau.
    assert "if (gesteADeplace) { gesteADeplace = false; return; }" in composant
