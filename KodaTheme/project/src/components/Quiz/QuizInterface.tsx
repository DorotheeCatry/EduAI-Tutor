import React, { useState } from 'react';
import { Brain, Users, Trophy, Clock, Play } from 'lucide-react';

export default function QuizInterface() {
  const [mode, setMode] = useState<'select' | 'solo' | 'multiplayer'>('select');
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [score, setScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(30);

  const questions = [
    {
      text: "Quelle est la différence entre POST et PUT ?",
      options: [
        "POST crée, PUT modifie",
        "POST modifie, PUT crée",
        "Aucune différence",
        "POST est plus sécurisé"
      ],
      correct: 0
    },
    {
      text: "Qu'est-ce qu'une closure en JavaScript ?",
      options: [
        "Une fonction qui ferme le navigateur",
        "Une fonction qui a accès aux variables de son scope parent",
        "Une fonction anonyme",
        "Une fonction récursive"
      ],
      correct: 1
    }
  ];

  const handleModeSelect = (selectedMode: 'solo' | 'multiplayer') => {
    setMode(selectedMode);
  };

  const handleAnswer = (answerIndex: number) => {
    if (answerIndex === questions[currentQuestion].correct) {
      setScore(score + 1);
    }
    
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setTimeLeft(30);
    } else {
      // Quiz terminé
      setMode('select');
      setCurrentQuestion(0);
      setScore(0);
    }
  };

  if (mode === 'select') {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center space-x-3 mb-6">
          <Brain className="w-6 h-6 text-primary-rose" />
          <h1 className="text-2xl font-bold text-white">Quiz & QCM</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div
            onClick={() => handleModeSelect('solo')}
            className="bg-gray-800 rounded-lg p-8 border border-gray-700 cursor-pointer transition-all duration-200 hover:border-primary-green hover:bg-gray-750 hover:scale-[1.02] group"
          >
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary-green bg-opacity-20 rounded-full flex items-center justify-center mx-auto group-hover:bg-opacity-30 transition-all duration-200">
                <Play className="w-8 h-8 text-primary-green" />
              </div>
              <h3 className="text-xl font-bold text-white">Mode Solo</h3>
              <p className="text-gray-400">Entraînez-vous à votre rythme avec des quiz personnalisés</p>
              <div className="flex justify-center space-x-4 text-sm text-gray-500">
                <span>• Temps illimité</span>
                <span>• Feedback instantané</span>
              </div>
            </div>
          </div>

          <div
            onClick={() => handleModeSelect('multiplayer')}
            className="bg-gray-800 rounded-lg p-8 border border-gray-700 cursor-pointer transition-all duration-200 hover:border-primary-blue hover:bg-gray-750 hover:scale-[1.02] group"
          >
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary-blue bg-opacity-20 rounded-full flex items-center justify-center mx-auto group-hover:bg-opacity-30 transition-all duration-200">
                <Users className="w-8 h-8 text-primary-blue" />
              </div>
              <h3 className="text-xl font-bold text-white">Mode Multijoueur</h3>
              <p className="text-gray-400">Défiez d'autres joueurs en temps réel</p>
              <div className="flex justify-center space-x-4 text-sm text-gray-500">
                <span>• Classement live</span>
                <span>• Compétition</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Trophy className="w-5 h-5 text-primary-rose" />
            <h3 className="text-lg font-semibold text-white">Statistiques</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-green">127</div>
              <div className="text-sm text-gray-400">Quiz terminés</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-blue">85%</div>
              <div className="text-sm text-gray-400">Précision</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-rose">12</div>
              <div className="text-sm text-gray-400">Série actuelle</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-gray">3h 42m</div>
              <div className="text-sm text-gray-400">Temps total</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Brain className="w-6 h-6 text-primary-rose" />
          <h1 className="text-2xl font-bold text-white">Quiz en cours</h1>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Clock className="w-5 h-5 text-primary-blue" />
            <span className="text-primary-blue font-mono text-lg">{timeLeft}s</span>
          </div>
          <div className="text-white">
            Question {currentQuestion + 1}/{questions.length}
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700">
        <div className="mb-8">
          <div className="w-full bg-gray-700 rounded-full h-2 mb-4">
            <div 
              className="bg-primary-green h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }}
            />
          </div>
          <h2 className="text-2xl font-bold text-white mb-6">
            {questions[currentQuestion].text}
          </h2>
        </div>

        <div className="space-y-4">
          {questions[currentQuestion].options.map((option, index) => (
            <button
              key={index}
              onClick={() => handleAnswer(index)}
              className="w-full p-4 text-left bg-gray-900 border border-gray-600 rounded-lg text-white hover:border-primary-green hover:bg-gray-850 transition-all duration-200 transform hover:scale-[1.01]"
            >
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">
                  {String.fromCharCode(65 + index)}
                </div>
                <span>{option}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-between items-center">
        <button
          onClick={() => setMode('select')}
          className="px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
        >
          Retour
        </button>
        <div className="text-white font-semibold">
          Score: {score}/{questions.length}
        </div>
      </div>
    </div>
  );
}