import React from 'react';
import { 
  BookOpen, 
  Search, 
  Brain, 
  BarChart3, 
  RotateCcw, 
  Settings,
  Code
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const menuItems = [
  { id: 'courses', label: 'Cours', icon: BookOpen },
  { id: 'search', label: 'Recherche', icon: Search },
  { id: 'quiz', label: 'Quiz', icon: Brain },
  { id: 'performance', label: 'Performances', icon: BarChart3 },
  { id: 'revision', label: 'Révision', icon: RotateCcw },
  { id: 'settings', label: 'Paramètres', icon: Settings },
];

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <div className="w-16 bg-gray-900 border-r border-gray-800 flex flex-col items-center py-4 space-y-2">
      <div className="mb-6">
        <Code className="w-8 h-8 text-primary-green" />
      </div>
      
      {menuItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`
              w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-200
              ${isActive 
                ? 'bg-primary-green bg-opacity-20 text-primary-green border border-primary-green border-opacity-30' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }
            `}
            title={item.label}
          >
            <Icon className="w-5 h-5" />
          </button>
        );
      })}
    </div>
  );
}