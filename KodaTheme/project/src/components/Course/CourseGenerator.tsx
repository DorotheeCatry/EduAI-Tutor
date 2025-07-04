import React, { useState } from 'react';
import { BookOpen, Sparkles, Play, Clock, BarChart } from 'lucide-react';

export default function CourseGenerator() {
  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState('intermediate');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    
    setIsGenerating(true);
    // Simulate AI generation
    await new Promise(resolve => setTimeout(resolve, 2000));
    setIsGenerating(false);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center space-x-3 mb-6">
        <BookOpen className="w-6 h-6 text-primary-green" />
        <h1 className="text-2xl font-bold text-white">Génération de Cours</h1>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Sujet du cours
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Ex: Les décorateurs Python, API REST avec FastAPI..."
              className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Niveau de difficulté
            </label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-primary-green focus:ring-1 focus:ring-primary-green transition-colors"
            >
              <option value="beginner">Débutant</option>
              <option value="intermediate">Intermédiaire</option>
              <option value="advanced">Avancé</option>
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={!topic.trim() || isGenerating}
            className={`
              w-full py-3 px-6 rounded-lg font-medium transition-all duration-200
              ${isGenerating
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-primary-green text-white hover:bg-green-600 hover:scale-[1.02] active:scale-[0.98]'
              }
            `}
          >
            {isGenerating ? (
              <div className="flex items-center justify-center space-x-2">
                <Sparkles className="w-5 h-5 animate-spin" />
                <span>Génération en cours...</span>
              </div>
            ) : (
              <div className="flex items-center justify-center space-x-2">
                <Sparkles className="w-5 h-5" />
                <span>Générer le cours</span>
              </div>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Play className="w-5 h-5 text-primary-blue" />
            <h3 className="text-lg font-semibold text-white">Cours Récents</h3>
          </div>
          <div className="space-y-3">
            {[
              { title: 'Décorateurs Python', progress: 85 },
              { title: 'API REST', progress: 60 },
              { title: 'React Hooks', progress: 45 },
            ].map((course, index) => (
              <div key={index} className="p-3 bg-gray-900 rounded-lg border border-gray-600">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-white">{course.title}</span>
                  <span className="text-xs text-gray-400">{course.progress}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div 
                    className="bg-primary-green h-2 rounded-full transition-all duration-300"
                    style={{ width: `${course.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Clock className="w-5 h-5 text-primary-rose" />
            <h3 className="text-lg font-semibold text-white">Temps d'étude</h3>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-primary-rose mb-2">2h 34m</div>
            <div className="text-sm text-gray-400">Aujourd'hui</div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <BarChart className="w-5 h-5 text-primary-blue" />
            <h3 className="text-lg font-semibold text-white">Progression</h3>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-primary-blue mb-2">67%</div>
            <div className="text-sm text-gray-400">Moyenne générale</div>
          </div>
        </div>
      </div>
    </div>
  );
}
