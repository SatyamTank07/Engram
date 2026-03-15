'use client';

import { AlertTriangle } from 'lucide-react';

export default function PersonsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      className="flex h-screen items-center justify-center animate-fadeIn"
      style={{ background: 'var(--background)' }}
    >
      <div className="text-center max-w-md px-6">
        <div
          className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--destructive-light)', color: 'var(--destructive)' }}
        >
          <AlertTriangle size={28} />
        </div>
        <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--foreground)' }}>
          Failed to load persons
        </h2>
        <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
          {error.message || 'An unexpected error occurred.'}
        </p>
        <button
          onClick={reset}
          className="px-5 py-2.5 text-sm font-medium text-white rounded-lg transition-colors active:scale-95 focus-visible:ring-2"
          style={{ background: 'var(--accent)' }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
