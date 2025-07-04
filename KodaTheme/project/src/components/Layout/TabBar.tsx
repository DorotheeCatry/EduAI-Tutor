import React from 'react';
import { X } from 'lucide-react';

interface Tab {
  id: string;
  title: string;
  modified?: boolean;
}

interface TabBarProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
}

export default function TabBar({ tabs, activeTab, onTabChange, onTabClose }: TabBarProps) {
  return (
    <div className="h-10 bg-gray-800 border-b border-gray-700 flex items-center">
      <div className="flex">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`
              h-10 px-4 flex items-center text-sm border-r border-gray-700 cursor-pointer
              transition-colors duration-150 group relative
              ${activeTab === tab.id 
                ? 'bg-gray-900 text-white' 
                : 'bg-gray-800 text-gray-300 hover:bg-gray-750'
              }
            `}
            onClick={() => onTabChange(tab.id)}
          >
            <span className="mr-2 truncate max-w-32">{tab.title}</span>
            {tab.modified && (
              <div className="w-2 h-2 bg-primary-green rounded-full mr-2" />
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onTabClose(tab.id);
              }}
              className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 p-1 hover:bg-gray-600 rounded"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}