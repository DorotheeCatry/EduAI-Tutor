# 🎓 EduAI Tutor – AI-Powered Educational Platform

## 🧭 Project Overview

EduAI Tutor is an intelligent educational web platform powered by multi-agent AI architecture. It enables learners to efficiently master development skills (Python, Django, FastAPI, etc.) through:

- **Dynamic course generation** with AI
- **Interactive quizzes** (solo and multiplayer)
- **Intelligent search** (educational chatbot with RAG)
- **Personalized revision** based on learning analytics
- **Code exercises** with automated testing

Built with **Django** and integrates generative AI components via **LangChain + Groq/Ollama**.

---

## 🧠 AI Architecture – Specialized Multi-Agent System

| AI Agent | Role | Main Function |
|----------|------|---------------|
| 🔍 **Researcher** | Information Retriever | Searches and retrieves relevant educational resources using RAG |
| 📖 **Pedagogue** | Content Synthesizer | Generates structured courses from retrieved resources |
| 🎯 **Coach** | Exercise Generator | Creates MCQs, code exercises, and practice problems |
| 📊 **Watcher** | Analytics & Tracking | Monitors performance, detects learning gaps, triggers revision |

---

## 🚀 Core Features

### 1. 📖 On-Demand Course Generation
- User selects a topic (e.g., "Python decorators")
- AI generates complete structured course: introduction, explanations, examples, summary
- **Agents involved**: Researcher + Pedagogue

### 2. 🔍 Intelligent Search (Educational Chatbot)
- Users ask questions freely (e.g., "What's the difference between POST and PUT?")
- AI uses **RAG engine** to search knowledge base and synthesize answers
- **Agents involved**: Researcher + Pedagogue

### 3. 📝 Interactive Quizzes (Solo & Multiplayer)
- **Solo Mode**: Individual training with personalized MCQs
- **Multiplayer Mode**: Real-time Kahoot-style competitions with live leaderboard
- Dynamic question generation based on topics
- **Agent involved**: Coach

### 4. 💻 Code Exercises
- Python programming exercises with automated testing
- Secure code execution environment
- Monaco Editor integration for better coding experience
- Progress tracking and performance analytics
- **Agent involved**: Coach

### 5. 📊 Performance Analytics
- Comprehensive learning dashboard
- Error analysis and response time tracking
- XP system with levels and achievements
- Streak tracking and goal setting
- **Agent involved**: Watcher

### 6. 🔁 Intelligent Revision System
- Spaced repetition flashcards (Anki-style)
- Targeted mini-quizzes for identified weak areas
- Personalized revision recommendations
- **Agents involved**: Watcher + Coach

---

## 🏗️ Project Structure

```
eduai-tutor/
│
├── apps/                           # Django applications
│   ├── agents/                     # AI multi-agent orchestration
│   │   ├── agent_orchestrator.py   # Main AI coordinator
│   │   ├── agent_researcher.py     # RAG-based information retrieval
│   │   ├── agent_pedagogue.py      # Course content generation
│   │   ├── agent_coach.py          # Quiz and exercise generation
│   │   ├── agent_watcher.py        # Learning analytics and tracking
│   │   ├── prompts/                # AI prompt templates
│   │   └── tools/                  # LLM utilities and loaders
│   │
│   ├── courses/                    # Course generation and management
│   │   ├── models.py               # Course and section models
│   │   ├── views.py                # Course generation logic
│   │   └── templates/              # Course display templates
│   │
│   ├── quiz/                       # Quiz system (solo & multiplayer)
│   │   ├── models.py               # Game rooms, questions, answers
│   │   ├── views.py                # Quiz logic and multiplayer
│   │   ├── consumers.py            # WebSocket handlers for real-time
│   │   └── templates/              # Quiz interfaces
│   │
│   ├── exercises/                  # Code exercise system
│   │   ├── models.py               # Exercise, submission, progress models
│   │   ├── views.py                # Exercise logic and code execution
│   │   ├── security.py             # Secure Python code execution
│   │   └── templates/              # Exercise interfaces
│   │
│   ├── chat/                       # Educational AI chatbot
│   │   ├── views.py                # Chat API and interface
│   │   └── templates/              # Chat interface
│   │
│   ├── users/                      # User management and authentication
│   │   ├── models.py               # Custom user model with XP system
│   │   ├── views.py                # Auth views and profile management
│   │   ├── forms.py                # Custom auth forms
│   │   └── templates/              # Auth and profile templates
│   │
│   ├── tracker/                    # Performance tracking and analytics
│   │   ├── views.py                # Dashboard and statistics
│   │   └── templates/              # Analytics dashboard
│   │
│   ├── revision/                   # Intelligent revision system
│   │   ├── views.py                # Revision logic
│   │   └── templates/              # Revision interfaces
│   │
│   └── rag/                        # Vector search and knowledge base
│       ├── utils.py                # Embedding and vector store utilities
│       ├── module_loader.py        # Dynamic module loading
│       └── scripts/                # Data preparation scripts
│
├── templates/                      # Global templates
│   ├── base.html                   # Main layout template
│   └── components/                 # Reusable UI components
│       ├── sidebar.html            # Navigation sidebar
│       ├── tabbar.html             # Dynamic tab management
│       ├── statusbar.html          # Status and progress bar
│       └── xp_notification.html    # XP and level-up notifications
│
├── theme/                          # Tailwind CSS theme
│   └── static_src/                 # Tailwind source files
│
├── static/                         # Static assets
│   ├── css/                        # Custom CSS
│   ├── img/                        # Images
│   └── koda/                       # Avatar collection
│
├── eduai_project/                  # Django project configuration
│   ├── settings.py                 # Project settings
│   ├── urls.py                     # URL routing
│   └── asgi.py                     # ASGI config for WebSockets
│
├── pyproject.toml                  # Dependencies (Poetry)
└── manage.py                       # Django management
```

---

## 🛠️ Technology Stack

### Backend
- **Framework**: Django 5.2+ with Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **AI/NLP**: LangChain + Groq API (with Ollama fallback)
- **Vector Search**: ChromaDB for RAG implementation
- **Real-time**: Django Channels + Redis for multiplayer features

### Frontend
- **Templates**: Django templates with Tailwind CSS
- **Icons**: Lucide Icons
- **Code Editor**: Monaco Editor for exercises
- **Syntax Highlighting**: Prism.js
- **Real-time**: WebSockets for multiplayer quizzes

### AI & Machine Learning
- **LLM Provider**: Groq (primary) / Ollama (fallback)
- **Embeddings**: Ollama embeddings for vector search
- **Code Execution**: Secure Python sandbox with RestrictedPython

---

## 🎯 User Journey

1. **Authentication**: User registers/logs in with email or username
2. **Course Generation**: Choose topic → AI generates comprehensive course
3. **Interactive Learning**: Read course, ask questions via AI chat
4. **Practice**: Take quizzes (solo/multiplayer) and solve code exercises
5. **Analytics**: View progress, identify weak areas
6. **Revision**: Use intelligent flashcards and targeted practice

---

## 🔧 Installation & Setup

### Prerequisites
- Python 3.12+
- Node.js 18+ (for Tailwind CSS)
- Redis (for multiplayer features)
- Ollama (optional, for local LLM)

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd eduai-tutor
```

2. **Install Python dependencies**
```bash
pip install -e .
```

3. **Install frontend dependencies**
```bash
cd theme/static_src
npm install
cd ../..
```

4. **Environment setup**
```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

5. **Database setup**
```bash
python manage.py migrate
python manage.py createsuperuser
```

6. **Start development servers**
```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Tailwind CSS
cd theme/static_src
npm run dev

# Terminal 3: Redis (for multiplayer)
redis-server
```

7. **Access the application**
- Open http://127.0.0.1:8000
- Register a new account or use superuser credentials

---

## 🎨 Feuille de style (Tailwind)

La feuille est **compilée hors ligne** et versionnée : `static/css/tailwind.css`.
Les gabarits la lient par `{% static %}` ; aucune page ne charge plus
`cdn.tailwindcss.com`.

### Reconstruire après avoir ajouté une classe

```bash
bash theme/tailwind-v3/construire.sh
```

Le script télécharge au besoin le binaire autonome de Tailwind 3.4.17 (43 Mio,
non versionné) et régénère la feuille depuis `theme/tailwind-v3/`.

**À lancer après toute modification de gabarit introduisant une classe
nouvelle.** Sans reconstruction, la classe ne produit aucun style et rien ne le
signale : la page s'affiche, simplement de travers. Le test
`tests/test_coquille_interface.py` échoue dans ce cas — il compare toutes les
classes des gabarits au contenu de la feuille.

### Ce qui est versionné

La feuille compilée, comme les catalogues `.mo` : l'image de déploiement est
bâtie sur le clone, et une feuille absente donnerait une application sans
styles que personne ne verrait avant la démonstration.

### Pourquoi pas `manage.py tailwind build`

`django-tailwind` est bien installé, mais son nécessaire est en **Tailwind 4**
alors que l'application a toujours été rendue en **3.4.17** ; et sa
construction échoue sur le Node 12 de la machine. Le binaire autonome produit
exactement la version que servait le CDN — équivalence vérifiée en comparant la
géométrie de tous les éléments sur six pages (décision 034).

### Où sont les classes

Le champ `content` de `theme/tailwind-v3/tailwind.config.js` couvre les
gabarits **et** `apps/**/*.py` : les widgets de formulaire déclarent leurs
classes en Python. Un chemin oublié donne une page sans styles.

---

## 🌍 Internationalisation (français / anglais)

L'interface est servie en **français par défaut**, en anglais si le compte le
demande. La langue vient de `language_preference`, un champ du compte, appliqué
à chaque requête par `apps.users.middleware.LangueDeLApprenant`. Elle suit donc
la personne d'un poste à l'autre, contrairement à un cookie.

Les catalogues vivent à **un seul endroit** : `locale/fr/` et `locale/en/`.

### Mettre à jour les traductions

**Toute chaîne ajoutée dans un gabarit ou dans du code Python doit passer par
ces trois commandes.** Un `.po` non régénéré n'échoue pas : la chaîne s'affiche
simplement dans sa langue source, au milieu du reste. C'est un écart
silencieux, et ce projet en a documenté assez pour ne pas en ajouter un.

```bash
# 1. Relever les chaînes nouvelles ou modifiées dans les deux catalogues
uv run python manage.py makemessages -l fr -l en \
    --ignore=.venv --ignore=staticfiles --ignore=node_modules \
    --ignore=theme/static --ignore=data_pipeline --ignore=benchmark

# 2. Traduire : éditer locale/fr/LC_MESSAGES/django.po et locale/en/…
#    Une entrée msgstr vide signifie « utiliser la chaîne source ».

# 3. Compiler — sans cette étape, la traduction reste sans effet
uv run python manage.py compilemessages --ignore=.venv
```

Les `--ignore` ne sont pas décoratifs : sans eux, `makemessages` parcourt
l'environnement virtuel et les dépendances, et `compilemessages` recompile les
catalogues de Django lui-même.

### Ce qui est versionné

Les `.po` **et** les `.mo`. Les fichiers compilés sont habituellement exclus
d'un dépôt, mais les images de déploiement sont construites à partir du clone :
sans les `.mo`, l'application déployée servirait ses chaînes sources, et
personne ne le verrait avant la démonstration.

### Écrire une chaîne traduisible

```django
{% load i18n %}
{% trans "Enregistrer" %}
{% blocktrans with nom=user.username %}Bonjour {{ nom }}{% endblocktrans %}
{% blocktrans count n=nombre %}{{ n }} cours{% plural %}{{ n }} cours{% endblocktrans %}
```

```python
from django.utils.translation import gettext as _
messages.success(request, _("Cours enregistré."))
messages.error(request, _("Erreur : %(motif)s") % {"motif": motif})
```

**Substitution nommée, jamais positionnelle** : `%(motif)s` peut changer de
place dans une traduction, `%s` non.

**Le signe pour cent ne survit pas à `{% trans %}`.** Écrit dans un gabarit,
`{% trans "%(joueur)s a gagné" %}` produit dans le catalogue l'identifiant
`%%(joueur)s a gagné`, doublé, alors que l'exécution demandera la version
simple. La traduction n'est jamais trouvée, et **rien ne le signale** : la
chaîne source s'affiche, ce qui passe inaperçu tant que la langue source est
celle qu'on regarde. Dans une chaîne de gabarit destinée à recevoir une valeur
côté navigateur, employer un repère neutre — `{joueur}` — et le remplacer en
JavaScript.

**Les chaînes assemblées en JavaScript se déclarent en tête du gabarit**, avec
`{% trans "…" as libelle %}`, puis se lisent avec `{{ libelle|escapejs }}`.
Sans `escapejs`, une apostrophe française suffit à casser la chaîne JavaScript
qui la porte.

### Ce qui n'est pas traduit, et pourquoi

Les messages d'erreur des deux API, les journaux, la documentation et le corpus
documentaire. Les motifs sont écrits dans `docs/decisions/025-portee-de-la-traduction.md`
et `docs/reserves.md` (réserve 10).

### Vérifier

```bash
DJANGO_DEBUG=False uv run pytest tests/test_i18n.py
```

Ces tests portent sur l'**effet** du réglage sur la page servie, jamais sur sa
présence en base : le champ `language_preference` existait depuis l'origine et
n'était lu par personne pour l'affichage.

---

## 🧪 Key Features in Detail

### Multi-Agent AI System
- **Orchestrator**: Coordinates all AI agents based on user requests
- **RAG Integration**: Vector search through educational content
- **Dynamic Content**: Courses and quizzes generated in real-time
- **Language Flexibility**: Content generated in user's preferred language

### Gamification & Progress
- **XP System**: Earn experience points for all activities
- **Levels & Titles**: Progress from Beginner to Legend
- **Streaks**: Daily learning streak tracking
- **Achievements**: Unlock titles and badges

### Real-time Multiplayer
- **WebSocket Integration**: Live quiz competitions
- **Room System**: Create/join quiz rooms with codes
- **Live Leaderboard**: Real-time score updates
- **Synchronized Questions**: All players see questions simultaneously

### Secure Code Execution
- **Sandboxed Environment**: Safe Python code execution
- **Automated Testing**: Run predefined tests against user code
- **Performance Metrics**: Execution time and memory tracking
- **Monaco Editor**: Professional code editing experience

---

## 🔮 Future Enhancements

- [ ] **Advanced Analytics**: Learning path recommendations
- [ ] **Social Features**: Study groups and peer collaboration
- [ ] **Mobile App**: React Native companion app
- [ ] **More Languages**: Support for JavaScript, Java, C++
- [ ] **AI Tutoring**: Personalized 1-on-1 AI tutoring sessions
- [ ] **Integration**: LMS integration (Moodle, Canvas)
- [ ] **Certification**: Generate completion certificates

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **LangChain**: For the excellent AI framework
- **Groq**: For fast LLM inference
- **Django**: For the robust web framework
- **Tailwind CSS**: For the beautiful UI components
- **Monaco Editor**: For the professional code editing experience

---

**Built with ❤️ by the EduAI Team**