'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, Sun, Moon } from 'lucide-react';
import { useTheme } from '@/components/ThemeProvider';
import { login } from '@/lib/auth';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(phone, password);
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex animate-fadeIn"
      style={{ background: 'var(--background)' }}
    >
      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        className="fixed top-4 right-4 p-2.5 rounded-lg z-10 transition-colors focus-visible:ring-2"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          color: 'var(--foreground)',
        }}
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      >
        {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
      </button>

      {/* Left branding panel (desktop only) */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col items-center justify-center p-12"
        style={{
          background: 'linear-gradient(135deg, var(--accent-light), var(--surface-secondary))',
        }}
      >
        {/* Geometric brain icon */}
        <svg
          viewBox="0 0 80 80"
          className="w-24 h-24 mb-8"
          fill="none"
          style={{ color: 'var(--accent)' }}
        >
          <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="2" opacity="0.3" />
          <circle cx="40" cy="40" r="24" stroke="currentColor" strokeWidth="2" opacity="0.5" />
          <path d="M28 40c0-6.627 5.373-12 12-12s12 5.373 12 12-5.373 12-12 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="40" cy="28" r="3" fill="currentColor" />
          <circle cx="52" cy="40" r="3" fill="currentColor" />
          <circle cx="40" cy="52" r="3" fill="currentColor" />
          <circle cx="28" cy="40" r="3" fill="currentColor" />
          <line x1="40" y1="28" x2="52" y2="40" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
          <line x1="52" y1="40" x2="40" y2="52" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
          <line x1="40" y1="52" x2="28" y2="40" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
          <line x1="28" y1="40" x2="40" y2="28" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
        </svg>
        <h1 className="text-4xl font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          Engram
        </h1>
        <p className="text-lg text-center max-w-sm" style={{ color: 'var(--muted)' }}>
          Your AI-powered memory and conversation assistant. Remember everything, forget nothing.
        </p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-sm space-y-8">
          {/* Mobile branding */}
          <div className="lg:hidden text-center">
            <h1 className="text-3xl font-bold" style={{ color: 'var(--foreground)' }}>
              Engram
            </h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>
              Your AI memory assistant
            </p>
          </div>

          <div>
            <h2
              className="text-2xl font-bold lg:text-left text-center"
              style={{ color: 'var(--foreground)' }}
            >
              Sign in
            </h2>
            <p
              className="mt-1 text-sm lg:text-left text-center"
              style={{ color: 'var(--muted)' }}
            >
              Enter your credentials to continue
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="phone"
                className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--foreground)' }}
              >
                Phone Number
              </label>
              <input
                id="phone"
                name="phone"
                type="tel"
                autoComplete="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                style={{
                  border: '1px solid var(--input-border)',
                  background: 'var(--input-bg)',
                  color: 'var(--foreground)',
                }}
                placeholder="1234567890"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--foreground)' }}
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 pr-10 rounded-lg text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                  style={{
                    border: '1px solid var(--input-border)',
                    background: 'var(--input-bg)',
                    color: 'var(--foreground)',
                  }}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors focus-visible:ring-2"
                  style={{ color: 'var(--muted-foreground)' }}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                className="rounded-lg p-3 text-sm animate-scaleIn"
                style={{
                  background: 'var(--destructive-light)',
                  color: 'var(--destructive)',
                  border: '1px solid var(--destructive-border)',
                }}
                role="alert"
                aria-describedby="login-error"
              >
                <span id="login-error">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed active:scale-95 focus-visible:ring-2 focus-visible:ring-offset-1"
              style={{ background: 'var(--accent)' }}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
