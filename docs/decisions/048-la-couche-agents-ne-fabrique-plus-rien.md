# 048 — La couche agents ne fabrique plus rien, et ses replis existent vraiment

**Date :** 12/09/2026
**Compétences :** C10 (épreuve E3), C13 (E3), C21 (E5), C18 (E4), C20 (E5)

## Contexte

Relecture complète de `apps/agents/` après le correctif du gabarit d'invite
(décision 047). La couche est très inégale : les fichiers récents
(`model_config.py`, `apps/chat/contexte.py`, `service_ia/agents.py`) sont
solides, les plus anciens (`agent_coach.py`, `tools/llm_loader.py`) datent
d'avant que le projet ne se donne ses règles et n'avaient jamais été repris.

Cinq défauts, de nature différente.

**Le Coach fabriquait du contenu.** `generate_quiz` ne remontait pas ses
échecs : il rendait un quiz d'exemple — « Question d'exemple sur X », quatre
options « Option A » à « Option D », `correct_answer: 0`. L'application
l'affichait comme un vrai. Ce quiz était répondable et notable, et sa bonne
réponse était l'option A, choisie arbitrairement. L'apprenant qui répondait
autre chose enregistrait un `UserMistake`, qui alimente `notions_a_revoir`, que
Koda cite dans sa salutation : une erreur inventée devenait une notion à
revoir. `generate_code_exercise` faisait de même avec une solution
`print('Hello World')` et un test `{"input": "test", "expected": "result"}`.

C'est le huitième foyer de données fabriquées du projet, et le seul qui
**écrive** en base au lieu de seulement afficher.

**Le drapeau de repli local ne basculait rien.** `use_local_llm()` existait,
était documenté dans la décision 001, dans `docs/chaine_livraison.md` et dans
l'incident du 25/08, était testé — et n'était appelé par personne. `get_llm`
choisissait sur la seule présence de `GROQ_API_KEY`. Les tests éprouvaient la
lecture du drapeau, jamais son effet : ils passaient sur une fonctionnalité
absente. Le manque était noté au journal du 25/08 et n'avait pas été repris.

**Le repli Ollama ne pouvait pas aboutir.** Il recevait le `model_name` passé
en argument, c'est-à-dire un identifiant du catalogue Groq
(`openai/gpt-oss-120b`). Ollama ne sert aucun modèle portant ce nom : le repli
échouait sur la même erreur de nom de modèle que l'incident qu'il couvrait.

**Aucun appel au fournisseur n'avait de délai d'attente.** Un appel qui ne
revient pas immobilisait le worker Django qui l'attendait.

**`agent_orchestrator.py` déclarait un `logger` puis faisait treize `print`**,
émojis et `traceback.print_exc()` compris. Quatre de plus dans le Coach.

S'y ajoutent deux points de forme : une docstring annonçant « using Researcher
+ Pedagogue » pour une méthode qui n'appelle que le Pédagogue, et deux fichiers
de zéro octet (`agent_base.py`, `chains/rag_chain.py`).

## Options

1. **Traiter les points de forme seulement** et laisser les replis en l'état
   jusqu'après la soutenance.
2. **Rendre les échecs explicites et brancher ce qui est documenté**, sans
   ajouter de fonctionnalité ni de dépendance.
3. **Reprendre la couche agents**, avec une classe de base commune et une
   gestion d'erreurs unifiée.

## Option retenue

La deuxième.

`generate_quiz` et `generate_code_exercise` lèvent `GenerationImpossible` au
lieu d'inventer. `AIOrchestrator.create_quiz` traite cette exception à part des
autres et rend `{"questions": [], "error": <motif>}` — ce que les deux vues de
quiz savent déjà lire, puisqu'elles vérifient la liste avant d'en faire quoi
que ce soit.

`get_llm` consulte `use_local_llm()` **en premier**, avant la clé, et le client
Ollama reçoit `modele_local()` — lu dans `OLLAMA_MODEL`, distinct de
`DEFAULT_LLM_MODEL`. Les appels distants portent `timeout` et `max_retries`.

Les `print` de la couche deviennent des appels au `logger` déjà déclaré. La
docstring dit ce que fait la méthode. Les deux fichiers vides sont supprimés.

## Raisons

**Un repli silencieux qui se fait passer pour un résultat est pire qu'un
échec.** L'échec est une information : il s'affiche, il se journalise, il se
compte au monitorage. Le faux quiz n'était rien de tout cela — il ressemblait à
un succès, et c'est à ce titre qu'il entrait en base.

**La distinction avec le repli des exercices est nette, et elle est le
critère.** `apps/exercises/views.py` crée lui aussi un gabarit vide quand la
génération échoue. Il est conservé, parce qu'il **le dit** à l'apprenant par un
message d'avertissement et qu'il refuse de se rattacher à une compétence, donc
ne fait progresser personne. Un repli annoncé et neutralisé n'est pas une
donnée fabriquée.

**Un test vert sur une fonctionnalité absente est la pire assurance qui
soit.** Les trois tests du drapeau passaient depuis trois semaines sur du code
mort. Les nouveaux éprouvent le client réellement construit, pas la lecture
d'une variable.

**Le délai d'attente vient d'une mesure, pas d'un chiffre rond.** Les 90
latences relevées au monitorage donnent 1,52 s de médiane, 6,82 s au 95e
centile, 6,96 s au maximum. Soixante secondes place le seuil à près de neuf
fois le pire appel observé : il ne coupera pas une génération qui aboutit.

**Reprendre la couche entière n'était pas au programme.** Le cahier des charges
l'interdit explicitement à cette date, et l'architecture en place — quatre
agents, quatre rôles, un goulot de quota unique — n'a pas de défaut de
conception. Ce sont ses bords qui étaient fautifs.

## Les dépréciations LangChain, et le code mort

Ces deux points ont d'abord été écartés, puis traités le même jour sur décision
explicite. La première rédaction de cette décision les portait en « limite
connue », au motif que le cahier des charges interdit les dépendances nouvelles
et la suppression de code à cette date. L'arbitrage a été tranché dans l'autre
sens, et il est consigné ici parce qu'il corrige la lecture qui avait été faite
de ces interdits.

**Les trois classes dépréciées sont remplacées.** `ChatOllama`,
`OllamaEmbeddings` et `Chroma` étaient importées depuis `langchain-community`,
où elles sont dépréciées depuis LangChain 0.3.1 et disparaissent en 1.0. Elles
viennent désormais de `langchain-ollama` et `langchain-chroma` — les paquets que
LangChain désigne lui-même comme remplaçants. Aucune signature d'appel ne
change.

Vérifié plutôt que supposé, parce qu'un corpus vectoriel est la dernière chose
qu'on veut casser : les deux collections relisent à l'identique avec le nouveau
client — 387 fragments pour `eduai_knowledge_base`, 24 004 pour
`eduai_corpus_documentaire` — et les métadonnées d'attribution
(`code_licence`, `attribution_requise`) sont intactes. La suite complète ne
lève plus aucun avertissement de dépréciation LangChain.

**`generate_code_exercise` est supprimée**, avec `get_code_exercise_chain` et
son invite. Elle portait le même repli fabriqué que le quiz — solution attendue
`print('Hello World')`, test `{"input": "test", "expected": "result"}` — et
n'avait aucun appelant : la génération d'exercices de l'application passe par
`apps/exercises/views.py`.

Le raisonnement qui l'avait d'abord fait conserver était la règle d'or du
cahier des charges — vérifier qu'on ne supprime pas une preuve avant de
condenser. Vérification faite, ce n'en était pas une : la preuve de la
génération d'exercices est le chemin qui s'exécute, pas celui qui dort. Et une
seconde implémentation que personne n'exécute est du code que personne ne
corrige — ce qui est exactement ce qui lui était arrivé pendant trois semaines.
Un test empêche qu'elle revienne.

## Limite connue

L'exemption `F401` de `ruff` reste en place pour le dépôt : 50 imports
inutilisés subsistent dans du code antérieur au linter. La couche `apps/agents/`
en est nettoyée, et le motif de l'exemption a été réécrit — il décrivait un cas
réel pour couvrir tout autre chose.

`apps/rag/scripts/prepare_chroma.py` importe encore `TextLoader`,
`NotebookLoader` et `PyPDFLoader` depuis `langchain-community`. Ceux-là n'y sont
pas dépréciés : `langchain-community` reste leur domicile, et aucun paquet
dédié ne les reprend.
