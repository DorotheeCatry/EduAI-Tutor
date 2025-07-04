export interface Course {
  id: string;
  title: string;
  description: string;
  content: string;
  progress: number;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  estimatedTime: number;
}

export interface Question {
  id: string;
  text: string;
  options: string[];
  correctAnswer: number;
  explanation: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface Quiz {
  id: string;
  title: string;
  questions: Question[];
  timeLimit?: number;
  isMultiplayer?: boolean;
}

export interface Performance {
  totalQuizzes: number;
  averageScore: number;
  totalStudyTime: number;
  streakDays: number;
  weakAreas: string[];
  strongAreas: string[];
}

export interface ChatMessage {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

export interface RevisionCard {
  id: string;
  front: string;
  back: string;
  difficulty: number;
  nextReview: Date;
  topic: string;
}