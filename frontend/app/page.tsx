'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import SessionSidebar from '@/components/SessionSidebar';
import ChatInterface from '@/components/ChatInterface';
import ErrorBoundary from '@/components/ErrorBoundary';
import { isAuthenticated, logout } from '@/lib/auth';

export default function Home() {
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login');
    } else {
      setIsChecking(false);
    }
  }, [router]);

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const handleNewChat = () => {
    // Reset current session when creating new chat
    setCurrentSessionId(null);
  };

  if (isChecking) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="text-gray-900">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <ErrorBoundary fallback={<div className="w-72 bg-gray-50 p-4 text-sm text-gray-500">Sidebar failed to load. Please refresh.</div>}>
        <SessionSidebar
          currentSessionId={currentSessionId}
          onSessionSelect={setCurrentSessionId}
          onNewChat={handleNewChat}
          onLogout={handleLogout}
        />
      </ErrorBoundary>
      <ErrorBoundary>
        <ChatInterface sessionId={currentSessionId} />
      </ErrorBoundary>
    </div>
  );
}
