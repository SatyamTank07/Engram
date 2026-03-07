'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Session, getSessions, createSession, deleteSession } from '@/lib/api';

interface SessionSidebarProps {
    currentSessionId: number | null;
    onSessionSelect: (sessionId: number) => void;
    onNewChat: () => void;
    onLogout?: () => void;
}

export default function SessionSidebar({
    currentSessionId,
    onSessionSelect,
    onNewChat,
    onLogout
}: SessionSidebarProps) {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(true);

    const loadSessions = async () => {
        try {
            const data = await getSessions();
            setSessions(data);
        } catch (error) {
            console.error('Failed to load sessions:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSessions();
    }, []);

    const handleNewChat = async () => {
        try {
            const newSession = await createSession();
            setSessions([newSession, ...sessions]);
            onNewChat();
            onSessionSelect(newSession.id);
        } catch (error) {
            console.error('Failed to create session:', error);
        }
    };

    const handleDelete = async (sessionId: number, e: React.MouseEvent) => {
        e.stopPropagation();

        if (!confirm('Delete this conversation?')) return;

        try {
            await deleteSession(sessionId);
            setSessions(sessions.filter(s => s.id !== sessionId));
            if (currentSessionId === sessionId) {
                onSessionSelect(sessions[0]?.id || 0);
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
        }
    };

    if (loading) {
        return (
            <div className="w-64 bg-gray-50 border-r border-gray-200 p-4">
                <div className="animate-pulse">Loading...</div>
            </div>
        );
    }

    return (
        <div className="w-64 bg-gray-50 border-r border-gray-200 p-4 flex flex-col h-screen">
            <button
                onClick={handleNewChat}
                className="w-full bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded-md mb-2 transition-colors"
            >
                ➕ New Chat
            </button>

            <Link
                href="/persons"
                className="w-full block text-center bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded-md mb-4 transition-colors"
            >
                👥 People
            </Link>

            <div className="flex-1 overflow-y-auto space-y-2">
                {sessions.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center mt-4">
                        No conversations yet
                    </p>
                ) : (
                    sessions.map((session) => (
                        <div
                            key={session.id}
                            onClick={() => onSessionSelect(session.id)}
                            className={`
                flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors
                ${currentSessionId === session.id
                                    ? 'bg-blue-100 border border-blue-300'
                                    : 'bg-white hover:bg-gray-100 border border-gray-200'}
              `}
                        >
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                    {currentSessionId === session.id ? '📝' : '💭'} {session.title}
                                </p>
                            </div>
                            <button
                                onClick={(e) => handleDelete(session.id, e)}
                                className="ml-2 text-gray-400 hover:text-red-500 transition-colors"
                            >
                                🗑️
                            </button>
                        </div>
                    ))
                )}
            </div>

            {onLogout && (
                <button
                    onClick={onLogout}
                    className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-2 px-4 rounded-md mt-4 transition-colors"
                >
                    🚪 Logout
                </button>
            )}
        </div>
    );
}
