import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  viewId?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[ErrorBoundary] ${this.props.viewId ?? 'unknown'}:`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-panel rounded-2xl p-8 mt-6 text-center">
          <div className="text-2xl font-bold text-red-400 mb-2">Something went wrong</div>
          <p className="text-slate-400 mb-4">
            Route: <code className="text-slate-300">{this.props.viewId ?? 'unknown'}</code>
          </p>
          <pre className="text-xs text-slate-500 bg-slate-950/80 rounded-xl p-4 overflow-auto text-left max-h-40">
            {this.state.error?.message}
          </pre>
          <button
            className="mt-4 px-4 py-2 bg-brand-blue/20 text-brand-blue rounded-lg hover:bg-brand-blue/30 transition"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
