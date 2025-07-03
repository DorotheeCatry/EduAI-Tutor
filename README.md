# 🎓 EduAI Tutor – Tuteur pédagogique intelligent assisté par IA

## 🧭 Objectif du projet

EduAI Tutor est une plateforme web éducative propulsée par une intelligence artificielle multi-agents.  
Elle permet à tout apprenant de se former efficacement en développement (Python, FastAPI, etc.) grâce à :

- des **cours générés dynamiquement**,
- des **quiz interactifs** (en solo ou en groupe),
- une **recherche intelligente** (chatbot pédagogique),
- une **révision personnalisée** basée sur les erreurs.

Le tout est développé avec **Django** et intègre des composants IA générative via **LangChain + Mistral**.

---

## 🧠 Architecture IA – Multi-agents spécialisés

| Agent IA        | Rôle                      | Fonction principale                                               |
|------------------|---------------------------|-------------------------------------------------------------------|
| 🧠 Chercheur      | Retriever                 | Récupère les ressources pédagogiques pertinentes                  |
| 📖 Pédagogue      | Synthétiseur              | Génère un cours structuré à partir des ressources trouvées        |
| 🎯 Coach IA       | Générateur d’exercices    | Crée QCM, complétions, bugs à corriger                            |
| 📊 Surveillant (*)| Analyse & suivi           | Observe les performances, détecte les erreurs, déclenche la révision |

(*) optionnel dans un premier MVP

---

## 🧩 Fonctionnalités – Parcours logique

### 1. 📖 Génération de cours à la demande
- L’utilisateur choisit un thème (ex : décorateurs Python)
- L’IA génère un cours complet : introduction, explication, exemples, résumé
- Agents impliqués : **Chercheur + Pédagogue**

### 2. 🔍 Recherche intelligente (chatbot)
- L’utilisateur pose librement des questions (ex : “Différence POST/PUT ?”)
- L’IA utilise un moteur **RAG** pour chercher et synthétiser la réponse
- Agents impliqués : **Chercheur + Pédagogue**

### 3. 📝 Quiz & QCM (solo ou multi-joueurs)
- QCM générés dynamiquement à partir du cours ou du thème
- Mode **solo** pour l'entraînement individuel
- Mode **multi-joueurs** (type Kahoot!) avec classement en direct
- Agent impliqué : **Coach IA**

### 4. 📊 Suivi des performances
- Tableau de bord de progression
- Analyse des erreurs, temps de réponse, score global
- Agent impliqué : **Surveillant**

### 5. 🔁 Révision intelligente personnalisée
- Génération de cartes de révision (type Anki)
- Mini-quizz ciblés pour combler les lacunes détectées
- Agents impliqués : **Surveillant + Coach IA**

---

## 🏗️ Structure Django prévue

| App Django | Rôle |
|------------|------|
| `core`     | Authentification, interface utilisateur |
| `courses`  | Génération et affichage de cours        |
| `quiz`     | Gestion des QCM (solo & multi-joueurs)  |
| `revision` | Révision intelligente personnalisée      |
| `agents`   | Orchestration des agents IA (LangChain) |
| `rag`      | Embeddings, vector store, RAG           |
| `chat`     | Interface de recherche intelligente      |
| `tracker`  | Suivi de progression et erreurs         |

---

## 🧪 Technologies utilisées

- **Framework** : Django + Django Rest Framework
- **Base de données** : PostgreSQL
- **IA / NLP** : LangChain + Mistral (ou autre LLM open-source)
- **Recherche vectorielle** : FAISS ou ChromaDB
- **Frontend** : Django templates (MVP) ou Gradio / React
- **Déploiement** : Docker (local), Azure ou Railway

---

## ✅ Objectif MVP

- [x] Génération de cours à la demande  
- [x] QCM interactifs (solo & multi-joueur)  
- [x] Chatbot IA pour questions techniques (RAG)  
- [x] Révision automatique basée sur les erreurs

---

## 🧭 Parcours utilisateur type
- Je choisis un thème à apprendre
- Je consulte un cours généré par l’IA
- Je pose mes questions à l’IA via le chatbot
- Je m’entraîne avec des QCM (seul ou à plusieurs)
- Je consulte mes résultats et erreurs
- Je révise avec des cartes et quizz ciblés
- 

## Structure du Projet
eduai-tutor/
│
├── apps/
│   ├── core/             ← Authentification, pages générales, layout
│   ├── courses/          ← Génération + affichage de cours (Agent Chercheur + Pédagogue)
│   ├── quiz/             ← QCM, complétion de code, multi-joueur (Agent Coach)
│   ├── revision/         ← Révision intelligente, cartes Anki, feedback (Agent Coach + Surveillant)
│   ├── agents/           ← Logique multi-agents : prompts, orchestrations, LangChain
│   ├── rag/              ← Embeddings, VectorStore, gestion documents pour RAG
│   ├── chat/             ← Chatbot pédagogique (interface + appels RAG)
│   ├── tracker/          ← Suivi des réponses, score, erreurs (Agent Surveillant)
│   └── users/            ← Gestion des utilisateurs (profils, rôles)
│
├── eduai_project/        ← Fichiers settings Django, URLs racine
│
├── db.sqlite3            ← (à remplacer par PostgreSQL en prod)
├── manage.py
├── pyproject.toml        ← Tu utilises Poetry 👍
├── poetry.lock
└── .gitignore
