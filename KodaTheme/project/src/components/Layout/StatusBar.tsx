import React from 'react';
import { Wifi, Battery, Clock } from 'lucide-react';

export default function StatusBar() {
  const [currentTime, setCurrentTime] = React.useState(new Date());

  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="h-6 bg-primary-blue text-white text-xs flex items-center justify-between px-4">
      <div className="flex items-center space-x-4">
        <span className="flex items-center space-x-1">
          <Clock className="w-3 h-3" />
          <span>Session: 2h 34m</span>
        </span>
        <span>Niveau: Intermédiaire</span>
        <span className="text-primary-green">● En ligne</span>
      </div>
      
      <div className="flex items-center space-x-2">
        <span>{currentTime.toLocaleTimeString()}</span>
        <Wifi className="w-3 h-3" />
        <Battery className="w-3 h-3" />
      </div>
    </div>
  );
}