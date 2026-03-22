'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Menu } from 'lucide-react';
import SessionSidebar from '@/components/SessionSidebar';
import ChatInterface from '@/components/ChatInterface';
import ErrorBoundary from '@/components/ErrorBoundary';
import Skeleton from '@/components/Skeleton';
import { isAuthenticated, logout } from '@/lib/auth';

interface ChatLayoutProps {
  sessionId: string | null;
}

export default function ChatLayout({ sessionId }: ChatLayoutProps) {
  const [isChecking, setIsChecking] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);
  const router = useRouter();

  const handleMessageSent = useCallback(() => {
    setSidebarRefreshKey(k => k + 1);
  }, []);

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
    router.push('/');
  };

  const handleSessionSelect = (sessionId: string) => {
    router.push(`/chat/${sessionId}`);
    setSidebarOpen(false);
  };

  if (isChecking) {
    return (
      <div
        className="flex h-screen items-center justify-center"
        style={{ background: 'var(--background)' }}
      >
        <div className="space-y-4 w-full max-w-md px-6">
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-4 w-64 mx-auto" />
          <div className="flex gap-3 mt-8">
            <Skeleton className="h-[calc(100vh-200px)] w-64" />
            <Skeleton className="h-[calc(100vh-200px)] flex-1" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen" style={{ background: 'var(--background)' }}>
      {/* Mobile hamburger */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-3 left-3 z-40 p-2 rounded-lg md:hidden transition-colors focus-visible:ring-2"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          color: 'var(--foreground)',
        }}
        aria-label="Open sidebar"
      >
        <Menu size={20} />
      </button>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 md:hidden animate-fadeIn"
          style={{ background: 'var(--overlay-bg)' }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-200 ease-in-out
          md:relative md:translate-x-0 md:z-auto
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <ErrorBoundary
          fallback={
            <div
              className="w-72 p-4 text-sm"
              style={{ background: 'var(--sidebar-bg)', color: 'var(--muted)' }}
            >
              Sidebar failed to load. Please refresh.
            </div>
          }
        >
          <SessionSidebar
            currentSessionId={sessionId}
            onSessionSelect={handleSessionSelect}
            onNewChat={handleNewChat}
            onLogout={handleLogout}
            refreshKey={sidebarRefreshKey}
          />
        </ErrorBoundary>
      </div>

      {/* Main chat area */}
      <ErrorBoundary>
        <ChatInterface sessionId={sessionId} onMessageSent={handleMessageSent} />
      </ErrorBoundary>
    </div>
  );
}
