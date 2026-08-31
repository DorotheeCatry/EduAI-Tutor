#!/usr/bin/env bash
#
# Vérification d'un déploiement, sur son URL publique.
#
# Compétence visée : C13 (épreuve E3) — déploiement
# Compétences concernées : C9 (E2), C17 (E4), C20 (E5), C21 (E5)
#
# Pourquoi ce script existe : « le déploiement n'a pas renvoyé d'erreur » n'est
# pas une vérification. Ce projet a documenté sept incidents dont le motif
# commun est qu'une action et son effet ne coïncident pas sans qu'on aille le
# constater — un extracteur annonçant un succès à zéro enregistrement, un
# chargeur annonçant 6 836 documents sur une base vide, une sonde se déclarant
# branchée sans recevoir aucun rappel.
#
# Ce que ce script vérifie est donc l'EFFET, jamais la déclaration.
#
# Usage :
#   ./docker/verifier-deploiement.sh <url_web> [<url_service_ia>]
#
# Variables facultatives, chacune débloquant des contrôles supplémentaires :
#   SERVICE_IA_CLE           clé de service, pour les contrôles 5 et 6
#   EDUAI_UTILISATEUR        adresse de connexion d'un compte d'essai
#   EDUAI_MOT_DE_PASSE       son mot de passe, pour les contrôles 3 et 7
#   VERIFIER_GENERATION=1    déclenche une génération réelle — appel FACTURÉ
#
# Choix : les contrôles qui coûtent de l'argent ne s'exécutent pas par défaut.
# Motivation : une vérification qu'on hésite à relancer n'est pas relancée. Le
# contrôle de génération est donc explicite, et le script dit à chaque fois ce
# qu'il n'a pas vérifié plutôt que de le passer sous silence.

set -uo pipefail

# --- 1. Initialisation des dépendances et connexions externes ---

URL_WEB="${1:-}"
URL_IA="${2:-${URL_WEB}}"

if [ -z "${URL_WEB}" ]; then
    echo "Usage : $0 <url_web> [<url_service_ia>]" >&2
    echo "Exemple : $0 https://eduai.up.railway.app https://eduai-ia.up.railway.app" >&2
    exit 2
fi

URL_WEB="${URL_WEB%/}"
URL_IA="${URL_IA%/}"

command -v curl >/dev/null 2>&1 || { echo "curl est introuvable." >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 est introuvable." >&2; exit 2; }

COOKIES="$(mktemp)"
CORPS="$(mktemp)"
SANTE_FICHIER="$(mktemp)"
trap 'rm -f "${COOKIES}" "${CORPS}" "${SANTE_FICHIER}"' EXIT

REUSSIS=0
ECHOUES=0
NON_VERIFIES=0

vert()  { printf '  \033[32mOK\033[0m      %s\n' "$1"; REUSSIS=$((REUSSIS + 1)); }
rouge() { printf '  \033[31mECHEC\033[0m   %s\n' "$1"; ECHOUES=$((ECHOUES + 1)); }
gris()  { printf '  \033[33mNON VU\033[0m  %s\n' "$1"; NON_VERIFIES=$((NON_VERIFIES + 1)); }
# Une mesure n'est ni une réussite ni un échec : elle ne compte dans aucun des
# trois compteurs. Un seuil de démonstrabilité n'est pas un seuil de
# fonctionnement, et confondre les deux ferait échouer une vérification sur un
# service qui marche.
mesure() { printf '  \033[36mMESURE\033[0m  %s\n' "$1"; }
titre() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# `--fail` n'est PAS utilisé : ces contrôles s'intéressent aux codes de retour,
# y compris 301, 403 et 429, qui sont ici des résultats attendus et non des
# erreurs. C'est le contraire du besoin de la chaîne de livraison, où un code
# d'erreur doit interrompre.
code_http() {
    curl -s -o "${CORPS}" -w '%{http_code}' --max-time 30 "$@"
}

# --- 2. Règles logiques de traitement ---

# Contrôle 1 — HTTPS effectif
#
# Deux choses distinctes : que le certificat soit valide (curl échoue sinon), et
# qu'une requête en clair soit redirigée au lieu d'être servie. Un site qui
# répond en HTTPS mais sert aussi en clair laisse passer le cookie de session
# avant toute chance de le protéger.
titre "1. Transport HTTPS"

if curl -s -o /dev/null --max-time 30 "${URL_WEB}/auth/login/"; then
    vert "certificat TLS valide sur ${URL_WEB}"
else
    rouge "connexion TLS impossible sur ${URL_WEB}"
fi

URL_CLAIR="http://${URL_WEB#https://}"
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${URL_CLAIR}/auth/login/")
REDIRECTION=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 30 "${URL_CLAIR}/auth/login/")
case "${CODE}" in
    301|302|307|308)
        case "${REDIRECTION}" in
            https://*) vert "le trafic en clair est redirigé vers ${REDIRECTION}" ;;
            *)         rouge "redirection ${CODE} vers une cible non HTTPS : ${REDIRECTION}" ;;
        esac
        ;;
    000) gris "l'hôte ne répond pas en clair — le proxy refuse le port 80 (acceptable)" ;;
    200) rouge "la page est SERVIE en clair : SECURE_SSL_REDIRECT est inactif" ;;
    *)   rouge "réponse inattendue en clair : ${CODE}" ;;
esac

# Contrôle 2 — cookies Secure
#
# Le réglage `SESSION_COOKIE_SECURE` ne se constate pas dans une page : il se
# lit dans l'en-tête `Set-Cookie`. Un cookie sans l'attribut `Secure` est envoyé
# en clair à la première requête HTTP, quelle que soit la qualité du TLS.
titre "2. Attributs des cookies"

ENTETES=$(curl -s -D - -o /dev/null --max-time 30 "${URL_WEB}/auth/login/")
COOKIE_CSRF=$(printf '%s' "${ENTETES}" | grep -i '^set-cookie: csrftoken' || true)

if [ -z "${COOKIE_CSRF}" ]; then
    gris "aucun cookie CSRF posé sur la page de connexion"
else
    printf '%s' "${COOKIE_CSRF}" | grep -qi 'Secure' \
        && vert "le cookie CSRF porte Secure" \
        || rouge "le cookie CSRF ne porte PAS Secure"
    printf '%s' "${COOKIE_CSRF}" | grep -qi 'SameSite' \
        && vert "le cookie CSRF porte SameSite" \
        || gris "le cookie CSRF ne porte pas SameSite"
fi

# Contrôle 3 — pages authentifiées
#
# Deux moitiés, et la première compte autant que la seconde : une page protégée
# doit refuser l'anonyme AVANT de servir la personne connectée. Vérifier
# seulement qu'elle s'affiche une fois connecté ne dit rien du contrôle d'accès.
titre "3. Pages authentifiées"

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 \
            "${URL_WEB}/courses/generator/")
REDIRECTION=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 30 \
                   "${URL_WEB}/courses/generator/")
case "${REDIRECTION}" in
    *"/auth/login/"*) vert "l'anonyme est renvoyé vers la connexion (${CODE})" ;;
    *)
        if [ "${CODE}" = "200" ]; then
            rouge "la page de génération est servie SANS authentification"
        else
            gris "réponse ${CODE} vers ${REDIRECTION:-aucune redirection}"
        fi
        ;;
esac

CONNECTE=0
if [ -n "${EDUAI_UTILISATEUR:-}" ] && [ -n "${EDUAI_MOT_DE_PASSE:-}" ]; then
    rm -f "${COOKIES}"
    PAGE=$(curl -s -c "${COOKIES}" --max-time 30 "${URL_WEB}/auth/login/")
    JETON=$(printf '%s' "${PAGE}" \
            | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' \
            | head -1 | cut -d'"' -f4)

    # `Referer` est exigé par Django sur toute requête HTTPS : sa vérification
    # est une protection CSRF supplémentaire, et son absence produit un 403 qui
    # ressemble à un mauvais mot de passe.
    CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 \
                -b "${COOKIES}" -c "${COOKIES}" \
                -e "${URL_WEB}/auth/login/" \
                -d "csrfmiddlewaretoken=${JETON}" \
                -d "username=${EDUAI_UTILISATEUR}" \
                -d "password=${EDUAI_MOT_DE_PASSE}" \
                "${URL_WEB}/auth/login/")

    if grep -q 'sessionid' "${COOKIES}"; then
        vert "connexion aboutie, cookie de session posé"
        CONNECTE=1
        # Format Netscape : domaine, sous-domaines, chemin, SECURE, expiration,
        # nom, valeur. Le drapeau Secure est la 4e colonne — chercher « TRUE »
        # dans la ligne entière donnerait un faux positif sur la 2e.
        SECURE=$(awk '$6 == "sessionid" { print $4 }' "${COOKIES}" | head -1)
        [ "${SECURE}" = "TRUE" ] \
            && vert "le cookie de session porte Secure" \
            || rouge "le cookie de session ne porte PAS Secure (colonne Secure : ${SECURE:-absente})"
        CODE=$(code_http -b "${COOKIES}" "${URL_WEB}/courses/generator/")
        [ "${CODE}" = "200" ] \
            && vert "la page de génération répond 200 une fois connecté" \
            || rouge "page de génération : ${CODE} alors que la session est ouverte"
    else
        rouge "connexion refusée (${CODE}) — identifiants ou CSRF"
    fi
else
    gris "contrôles connectés sautés : EDUAI_UTILISATEUR et EDUAI_MOT_DE_PASSE absents"
fi

# Contrôle 4 — état du service IA et empreinte du corpus
#
# L'empreinte est le seul moyen de constater que le corpus déployé est celui du
# poste : depuis la décision 023, il voyage sur un volume et non dans l'image,
# donc rien ne garantit plus qu'ils correspondent.
titre "4. Service IA, corpus et empreinte"

CODE=$(code_http "${URL_IA}/ai/sante")
if [ "${CODE}" != "200" ]; then
    rouge "/ai/sante répond ${CODE}"
else
    SANTE=$(cat "${CORPS}")
    STATUT=$(printf '%s' "${SANTE}" | python3 -c "import json,sys; print(json.load(sys.stdin)['statut'])" 2>/dev/null)
    case "${STATUT}" in
        operationnel) vert "statut du service : operationnel" ;;
        degrade)      rouge "statut du service : degrade — corpus absent ou écritures du journal en échec" ;;
        *)            rouge "statut du service : ${STATUT:-illisible}" ;;
    esac

    # La réponse passe par un FICHIER et non par un tube : un script fourni en
    # heredoc occupe déjà l'entrée standard de python, et le tube y est
    # silencieusement remplacé. C'est ce qui a fait échouer le premier essai de
    # ce script — le contrôle affichait une erreur d'analyse JSON sur une
    # réponse pourtant valide.
    printf '%s' "${SANTE}" > "${SANTE_FICHIER}"
    python3 - "${SANTE_FICHIER}" "$(pwd)/apps/rag/chroma/EMPREINTE.json" <<'PYTHON'
import json
import sys
from pathlib import Path

distante = (json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
            .get("corpus_rag", {}).get("empreinte"))
if not distante:
    print("  \033[33mNON VU\033[0m  le corpus déployé ne porte pas d'empreinte")
    sys.exit(0)

collections = distante.get("collections", {})
print(f"  \033[32mOK\033[0m      corpus déployé du {distante['date_releve']}")
for nom, releve in collections.items():
    # Le relevé porte le décompte ET l'empreinte de la collection depuis le
    # 31/08 : l'empreinte ne se calcule plus sur les octets de SQLite, que la
    # moindre lecture réécrit.
    if isinstance(releve, dict):
        print(f"            {nom} : {releve['fragments']} fragments")
    else:
        print(f"            {nom} : absente")

chemin_local = Path(sys.argv[2])
if not chemin_local.is_file():
    print("  \033[33mNON VU\033[0m  aucune empreinte locale à comparer")
    sys.exit(0)

locale = json.loads(chemin_local.read_text(encoding="utf-8"))
if locale.get("empreinte_sha256") == distante.get("empreinte_sha256"):
    print("  \033[32mOK\033[0m      l'empreinte déployée est celle du poste")
else:
    print("  \033[31mECHEC\033[0m   le corpus déployé n'est PAS celui du poste")
    print(f"            poste   : {locale.get('date_releve')} "
          f"{str(locale.get('collections'))}")
    print(f"            serveur : {distante.get('date_releve')} "
          f"{str(distante.get('collections'))}")
PYTHON

    LIGNES_AVANT=$(printf '%s' "${SANTE}" | python3 -c \
        "import json,sys; print(json.load(sys.stdin)['monitorage']['lignes_ecrites_sur_disque'])" 2>/dev/null || echo 0)
fi

# Contrôle 5 — recherche RAG et attribution
#
# « Le RAG répond » ne suffit pas : une réponse sans source n'est pas
# attribuable, et c'est l'attribution qui distingue une recherche documentaire
# d'une génération plausible.
titre "5. Recherche documentaire et attribution"

if [ -z "${SERVICE_IA_CLE:-}" ]; then
    gris "contrôles de l'API sautés : SERVICE_IA_CLE absente"
else
    # Chronométré de bout en bout, et pas seulement côté serveur.
    #
    # Motivation : la recherche embarque la requête avant de chercher, et
    # l'embarquement chez l'hébergeur se fait sans GPU. Mesuré sur
    # /api/embeddings le 30/08 : 13,6 s pour 9 jetons, 52,2 s pour 343 jetons —
    # environ trois fois plus lent qu'en local. Une recherche qui aboutit mais
    # demande quarante secondes n'est pas démontrable devant un jury, et c'est
    # une information qu'aucun code de retour ne porte.
    DEBUT_RECHERCHE=$(date +%s)
    CODE=$(code_http -X POST -H "X-Cle-Service: ${SERVICE_IA_CLE}" \
                 -H "Content-Type: application/json" \
                 -d '{"requete": "les listes en python", "nombre_fragments": 3}' \
                 --max-time 120 \
                 "${URL_IA}/ai/recherche")
    DUREE_RECHERCHE=$(( $(date +%s) - DEBUT_RECHERCHE ))
    if [ "${CODE}" != "200" ]; then
        rouge "/ai/recherche répond ${CODE}"
    else
        mesure "recherche de bout en bout : ${DUREE_RECHERCHE} s"
        if [ "${DUREE_RECHERCHE}" -ge 15 ]; then
            mesure "au-delà de 15 s — à arbitrer avant la démonstration (réserve 7)"
        fi
        python3 - "${CORPS}" <<'PYTHON'
import json
import sys
from pathlib import Path

corps = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
fragments = corps.get("fragments", [])

if not fragments:
    print("  \033[31mECHEC\033[0m   la recherche n'a retourné AUCUN fragment")
    sys.exit(0)

print(f"  \033[32mOK\033[0m      {len(fragments)} fragments retournés")

# La latence que le service s'attribue, à côté de celle qu'on a chronométrée.
# L'écart entre les deux est le temps de transport et de mise en file : le
# distinguer évite d'imputer au modèle ce qui vient du réseau.
if "latence_secondes" in corps:
    print(f"  \033[36mMESURE\033[0m  dont {corps['latence_secondes']:.1f} s "
          f"comptés par le service lui-même")

# `source` est le champ du contrat (FragmentRAG), `metadonnees` le complète.
# Un fragment sans l'un ni l'autre n'est pas attribuable, et plusieurs licences
# du corpus exigent de pouvoir renvoyer vers l'origine.
attribues = [f for f in fragments if f.get("source") or f.get("metadonnees")]
if len(attribues) == len(fragments):
    print("  \033[32mOK\033[0m      chaque fragment porte une attribution")
else:
    print(f"  \033[31mECHEC\033[0m   {len(fragments) - len(attribues)} fragments sans attribution")
PYTHON
    fi
fi

# Contrôle 6 — génération réelle
#
# Le seul contrôle qui appelle le fournisseur, donc le seul qui coûte. Il est
# explicite : la vérification ne doit pas être ce qui vide le plafond du jour.
titre "6. Génération de cours"

if [ -z "${SERVICE_IA_CLE:-}" ]; then
    gris "génération non vérifiée : SERVICE_IA_CLE absente"
elif [ "${VERIFIER_GENERATION:-0}" != "1" ]; then
    gris "génération non vérifiée : appel facturé, relancer avec VERIFIER_GENERATION=1"
else
    DEBUT=$(date +%s)
    CODE=$(code_http -X POST -H "X-Cle-Service: ${SERVICE_IA_CLE}" \
                 -H "Content-Type: application/json" \
                 -d '{"sujet": "les listes en python"}' \
                 --max-time 180 "${URL_IA}/ai/cours")
    DUREE=$(( $(date +%s) - DEBUT ))
    case "${CODE}" in
        200)
            OCTETS=$(wc -c < "${CORPS}")
            if [ "${OCTETS}" -gt 200 ]; then
                vert "cours généré en ${DUREE} s (${OCTETS} octets)"
            else
                rouge "réponse 200 mais corps quasi vide (${OCTETS} octets)"
            fi
            ;;
        429) gris "quota atteint (429) — le plafond fonctionne, la génération reste non vérifiée" ;;
        *)   rouge "/ai/cours répond ${CODE}" ;;
    esac
fi

# Contrôle 7 — décompte de quota et journal de monitorage
#
# Le décompte affiché est ce que l'apprenant lit avant de demander : une valeur
# qui ne bouge pas est un compteur qui ne compte pas. Le journal, lui, est la
# preuve de C20 sur le serveur — le monitorage a déjà été en panne silencieuse
# une fois (incident 003), il ne se suppose pas.
titre "7. Quota affiché et journal de monitorage"

if [ "${CONNECTE}" = "1" ]; then
    CODE=$(code_http -b "${COOKIES}" "${URL_WEB}/courses/generator/")
    RESTE=$(grep -o 'Il vous reste[^<]*' "${CORPS}" | head -1)
    if [ -n "${RESTE}" ]; then
        vert "décompte affiché : « ${RESTE} »"
    else
        rouge "aucun décompte de générations affiché sur la page"
    fi
else
    gris "décompte non vérifié : aucune session ouverte"
fi

CODE=$(code_http "${URL_IA}/ai/sante")
if [ "${CODE}" = "200" ]; then
    LIGNES_APRES=$(python3 -c \
        "import json,sys; print(json.load(open('${CORPS}'))['monitorage']['lignes_ecrites_sur_disque'])" 2>/dev/null || echo 0)
    if [ "${LIGNES_APRES:-0}" -gt 0 ]; then
        vert "journal de monitorage : ${LIGNES_APRES} lignes écrites sur le serveur"
        if [ "${LIGNES_APRES}" -gt "${LIGNES_AVANT:-0}" ]; then
            vert "le journal s'est enrichi pendant cette vérification"
        else
            gris "le journal n'a pas bougé — aucun appel tracé n'a été déclenché ici"
        fi
    else
        rouge "aucune ligne écrite : la sonde est branchée sans effet (incident 003)"
    fi
fi

# --- 3. Gestion des erreurs et exceptions ---
# Aucun contrôle n'interrompt le script : un échec de transport ne doit pas
# masquer l'état du corpus, et une clé absente ne doit pas empêcher de vérifier
# le HTTPS. Le compte rendu final porte le verdict.

# --- 4. Sauvegarde des résultats ---

titre "Compte rendu"
printf '  %s réussis, %s en échec, %s non vérifiés\n' \
       "${REUSSIS}" "${ECHOUES}" "${NON_VERIFIES}"

if [ "${NON_VERIFIES}" -gt 0 ]; then
    echo
    echo "  Les contrôles « NON VU » ne sont pas des réussites. Pour les lever :"
    echo "    SERVICE_IA_CLE=…  EDUAI_UTILISATEUR=…  EDUAI_MOT_DE_PASSE=…  \\"
    echo "    VERIFIER_GENERATION=1  $0 ${URL_WEB} ${URL_IA}"
fi

echo
if [ "${ECHOUES}" -gt 0 ]; then
    echo "  Déploiement NON validé : ${ECHOUES} contrôle(s) en échec."
    exit 1
fi
echo "  Aucun échec. Ce qui a été vérifié l'a été sur l'URL publique."
exit 0
