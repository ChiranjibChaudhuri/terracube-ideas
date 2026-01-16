import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

/**
 * React Error Boundary component to catch rendering errors gracefully.
 * Prevents the entire app from crashing due to component errors.
 */
class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    private handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    public render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="error-boundary">
                    <div className="error-boundary__content">
                        <h2>Something went wrong</h2>
                        <p>An unexpected error occurred. Please try again.</p>
                        {this.state.error && (
                            <pre className="error-boundary__message">
                                {this.state.error.message}
                            </pre>
                        )}
                        <div className="error-boundary__actions">
                            <button onClick={this.handleReset} className="button-primary">
                                Try Again
                            </button>
                            <button onClick={() => window.location.reload()} className="button-secondary">
                                Reload Page
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
