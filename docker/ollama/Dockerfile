# Serveur d'embarquement pour le déploiement (C13).
#
# Compétence visée : C13 (épreuve E3) — déploiement
# Compétence visée : C10 (épreuve E3) — intégration du modèle
#
# Pourquoi ce service existe : le RAG embarque chaque requête avant de chercher
# dans le corpus. Sur le poste de développement, Ollama tourne sur la machine ;
# chez l'hébergeur, il n'y a rien sur la boucle locale, et la recherche
# documentaire échouerait à chaque appel.
#
# Pourquoi ce modèle et pas un autre : le corpus a été indexé avec
# `mxbai-embed-large`. Interroger ces vecteurs avec un autre modèle ne donne pas
# de moins bons résultats, il en donne des dénués de sens — les deux espaces
# vectoriels n'ont aucun rapport. Le modèle n'est donc pas un réglage : c'est
# une contrainte posée par l'indexation, et en changer impose de réindexer les
# 21 189 fragments (décision 021, plus de dix-sept heures).
#
# Voir docs/decisions/022-serveur-embarquement-en-service-dedie.md

# Version figée, et non `latest`. Un serveur d'embarquement qui change de
# version sans qu'aucun commit n'ait eu lieu ici est un service dont on ne peut
# pas expliquer le comportement. C'est la version en usage sur le poste de
# développement, donc celle sur laquelle le corpus a été construit.
FROM ollama/ollama:0.32.15

# Le modèle est téléchargé À LA CONSTRUCTION, pas au premier démarrage.
#
# Motivation : un téléchargement au démarrage ferait échouer la première
# recherche de chaque déploiement, le temps que 670 Mio arrivent — et
# échouerait tout court si le registre amont était indisponible ce jour-là.
# Construit dans l'image, le modèle est là ou l'image n'existe pas.
ARG MODELE_EMBARQUEMENT=mxbai-embed-large

# `ollama pull` a besoin d'un serveur en marche : il n'est pas un simple
# téléchargement, il dialogue avec l'API locale. D'où le démarrage temporaire,
# l'attente que l'API réponde, puis l'arrêt — le tout dans une seule
# instruction, pour que la couche produite ne contienne que le modèle.
RUN ollama serve & \
    for _ in $(seq 1 30); do \
        if ollama list >/dev/null 2>&1; then break; fi; \
        sleep 1; \
    done; \
    ollama pull "${MODELE_EMBARQUEMENT}" && \
    ollama list && \
    pkill -f "ollama serve"

EXPOSE 11434

# Écoute sur toutes les interfaces : le réseau privé de l'hébergeur est le seul
# à atteindre ce conteneur, et les deux services qui l'appellent y sont. Ce
# service ne doit recevoir aucun domaine public — il n'a ni authentification ni
# limitation de débit, et n'en a pas besoin tant qu'il reste sur ce réseau.
ENV OLLAMA_HOST=0.0.0.0:11434

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ollama list >/dev/null 2>&1 || exit 1
