'use client';

import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  showDetails: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex items-center justify-center p-8 animate-fadeIn">
          <div className="text-center max-w-md">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
              style={{ background: 'var(--warning-light)', color: 'var(--warning)' }}
            >
              <AlertTriangle size={24} />
            </div>
            <h3
              className="text-lg font-semibold mb-1"
              style={{ color: 'var(--foreground)' }}
            >
              Something went wrong
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              This section encountered an error.
            </p>
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => this.setState({ hasError: false, error: null, showDetails: false })}
                className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors active:scale-95 focus-visible:ring-2"
                style={{ background: 'var(--accent)' }}
              >
                Try again
              </button>
              {this.state.error && (
                <button
                  onClick={() => this.setState({ showDetails: !this.state.showDetails })}
                  className="px-4 py-2 text-sm rounded-lg transition-colors focus-visible:ring-2"
                  style={{
                    color: 'var(--muted)',
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                  }}
                >
                  {this.state.showDetails ? 'Hide details' : 'Show details'}
                </button>
              )}
            </div>
            {this.state.showDetails && this.state.error && (
              <pre
                className="mt-4 p-3 rounded-lg text-xs text-left overflow-x-auto"
                style={{
                  background: 'var(--surface-secondary)',
                  color: 'var(--destructive)',
                  border: '1px solid var(--border)',
                }}
              >
                {this.state.error.message}
                {'\n'}
                {this.state.error.stack}
              </pre>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
