import { Component, type ErrorInfo, type ReactNode } from 'react';
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Do not log request data or server responses. */ }
  render() {
    if (this.state.failed) return <main className="fatal-state"><h1>The workspace couldn’t load.</h1><p>Check the API configuration and reload the page. No simulation results have been substituted.</p><button className="button" onClick={() => window.location.reload()}>Reload workspace</button></main>;
    return this.props.children;
  }
}
