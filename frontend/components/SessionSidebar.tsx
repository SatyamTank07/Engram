'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import {
  Plus, Users, MessageSquare, Trash2, LogOut, Sun, Moon, Search,
  MessageSquarePlus, Lightbulb, BookOpen, Target,
} from 'lucide-react';
import { useTheme } from '@/components/ThemeProvider';
import ConfirmDialog from '@/components/ConfirmDialog';
import Skeleton from '@/components/Skeleton';
import { Session, getSessions, createSession, deleteSession } from '@/lib/api';

interface SessionSidebarProps {
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
  onLogout?: () => void;
  refreshKey?: number;
}

export default function SessionSidebar({
  currentSessionId,
  onSessionSelect,
  onNewChat,
  onLogout,
  refreshKey,
}: SessionSidebarProps) {
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch {
      toast.error('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [refreshKey]);

  const handleNewChat = async () => {
    try {
      const newSession = await createSession();
      setSessions([newSession, ...sessions]);
      router.push(`/chat/${newSession.id}`);
      toast.success('New chat created');
    } catch {
      toast.error('Failed to create session');
    }
  };

  const handleDeleteConfirm = async () => {
    if (deleteTarget === null) return;
    const sessionId = deleteTarget;
    setDeleteTarget(null);
    try {
      await deleteSession(sessionId);
      const remaining = sessions.filter(s => s.id !== sessionId);
      setSessions(remaining);
      if (currentSessionId === sessionId) {
        router.push('/');
      }
      toast.success('Conversation deleted');
    } catch {
      toast.error('Failed to delete session');
    }
  };

  const filteredSessions = sessions.filter(s =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div
        className="w-72 p-4 flex flex-col h-screen"
        style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}
      >
        <Skeleton className="h-10 w-full mb-2" />
        <Skeleton className="h-10 w-full mb-4" />
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        className="w-72 p-4 flex flex-col h-screen"
        style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}
      >
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg mb-2 text-sm font-medium text-white transition-colors active:scale-95 focus-visible:ring-2"
          style={{ background: 'var(--accent)' }}
          aria-label="New chat"
        >
          <Plus size={16} />
          New Chat
        </button>

        <div className="grid grid-cols-2 gap-1.5 mb-3">
          <Link
            href="/persons"
            className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-colors focus-visible:ring-2"
            style={{
              background: 'var(--surface)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          >
            <Users size={14} />
            People
          </Link>
          <Link
            href="/ideas"
            className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-colors focus-visible:ring-2"
            style={{
              background: 'var(--surface)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          >
            <Lightbulb size={14} />
            Ideas
          </Link>
          <Link
            href="/content"
            className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-colors focus-visible:ring-2"
            style={{
              background: 'var(--surface)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          >
            <BookOpen size={14} />
            Content
          </Link>
          <Link
            href="/projects"
            className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-colors focus-visible:ring-2"
            style={{
              background: 'var(--surface)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          >
            <Target size={14} />
            Projects
          </Link>
        </div>

        {/* Search sessions */}
        <div className="relative mb-3">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--muted-foreground)' }}
          />
          <input
            type="text"
            placeholder="Search chats..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-2 rounded-lg text-sm transition-colors focus:outline-none focus-visible:ring-2"
            style={{
              background: 'var(--input-bg)',
              border: '1px solid var(--border)',
              color: 'var(--foreground)',
            }}
            aria-label="Search conversations"
          />
        </div>

        <div className="flex-1 overflow-y-auto space-y-1">
          {filteredSessions.length === 0 ? (
            <div className="text-center mt-8 animate-fadeIn">
              <MessageSquarePlus
                size={32}
                className="mx-auto mb-2"
                style={{ color: 'var(--muted-foreground)' }}
              />
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                {searchQuery ? 'No matching chats' : 'No conversations yet'}
              </p>
              {!searchQuery && (
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  Start a new chat to begin
                </p>
              )}
            </div>
          ) : (
            filteredSessions.map(session => (
              <div
                key={session.id}
                onClick={() => onSessionSelect(session.id)}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onSessionSelect(session.id); }}
                tabIndex={0}
                role="button"
                aria-label={`Open session: ${session.title}`}
                className="flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-150 group focus-visible:ring-2"
                style={{
                  background: currentSessionId === session.id ? 'var(--accent-light)' : 'var(--surface)',
                  border: `1px solid ${currentSessionId === session.id ? 'var(--accent-border)' : 'var(--border)'}`,
                }}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <MessageSquare
                    size={14}
                    className="shrink-0"
                    style={{ color: currentSessionId === session.id ? 'var(--accent)' : 'var(--muted-foreground)' }}
                  />
                  <p
                    className="text-sm font-medium truncate"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {session.title}
                  </p>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); setDeleteTarget(session.id); }}
                  className="ml-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded focus-visible:ring-2 focus-visible:opacity-100"
                  style={{ color: 'var(--muted-foreground)' }}
                  aria-label={`Delete session: ${session.title}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Footer: theme toggle + logout */}
        <div className="pt-3 mt-2 space-y-2" style={{ borderTop: '1px solid var(--border)' }}>
          <button
            onClick={toggleTheme}
            className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm transition-colors focus-visible:ring-2"
            style={{
              background: 'var(--surface)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          >
            {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
          </button>

          {onLogout && (
            <button
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm transition-colors focus-visible:ring-2"
              style={{
                background: 'var(--surface)',
                color: 'var(--muted)',
                border: '1px solid var(--border)',
              }}
              aria-label="Log out"
            >
              <LogOut size={16} />
              Logout
            </button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete Conversation"
        message="This conversation will be permanently deleted. This action cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
