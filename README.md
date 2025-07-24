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