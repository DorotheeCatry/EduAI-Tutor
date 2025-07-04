import React, { useState } from 'react';
import Sidebar from './components/Layout/Sidebar';
import TabBar from './components/Layout/TabBar';
import StatusBar from './components/Layout/StatusBar';
import CourseGenerator from './components/Course/CourseGenerator';
import SearchChat from './components/Search/SearchChat';
import QuizInterface from './components/Quiz/QuizInterface';

interface Tab {
  id: string;
  title: string;
  component: React.ComponentType;
  modified?: boolean;
}

const tabComponents: Record<string, Tab> = {
  courses: {
    id: 'courses',
    title: 'Générateur de Cours',
    component: CourseGenerator,
  },
  search: {
    id: 'search',
    title: 'Recherche IA',
    component: SearchChat,
  },
  quiz: {
    id: 'quiz',
    title: 'Quiz & QCM',
    component: QuizInterface,
  },
  performance: {
    id: 'performance',
    title: 'Performances',
    component: () => (
      <div className="p-6 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Tableau de Bord</h2>
        <p className="text-gray-400">Analyse de performances en cours de développement...</p>
      </div>
    ),
  },
  revision: {
    id: 'revision',
    title: 'Révision',
    component: () => (
      <div className="p-6 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Révision Intelligente</h2>
        <p className="text-gray-400">Système de cartes de révision en cours de développement...</p>
      </div>
    ),
  },
  settings: {
    id: 'settings',
    title: 'Paramètres',
    component: () => (
      <div className="p-6 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Paramètres</h2>
        <p className="text-gray-400">Configuration de l'application...</p>
      </div>
    ),
  },
};

function App() {
  const [activeTab, setActiveTab] = useState('courses');
  const [openTabs, setOpenTabs] = useState<Tab[]>([tabComponents.courses]);

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    
    // Add tab if not already open
    if (!openTabs.find(tab => tab.id === tabId)) {
      setOpenTabs(prev => [...prev, tabComponents[tabId]]);
    }
  };

  const handleTabClose = (tabId: string) => {
    const newTabs = openTabs.filter(tab => tab.id !== tabId);
    setOpenTabs(newTabs);
    
    // If closing active tab, switch to first available tab
    if (activeTab === tabId && newTabs.length > 0) {
      setActiveTab(newTabs[0].id);
    }
  };

  const ActiveComponent = tabComponents[activeTab]?.component || (() => null);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      <div className="flex flex-1">
        <Sidebar activeTab={activeTab} onTabChange={handleTabChange} />
        
        <div className="flex-1 flex flex-col">
          <TabBar
            tabs={openTabs}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onTabClose={handleTabClose}
          />
          
          <div className="flex-1 overflow-hidden">
            <ActiveComponent />
          </div>
        </div>
      </div>
      
      <StatusBar />
    </div>
  );
}

export default App;