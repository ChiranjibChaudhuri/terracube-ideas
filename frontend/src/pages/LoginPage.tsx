import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../lib/api';

const LoginPage = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [redirectMessage, setRedirectMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const reason = sessionStorage.getItem('auth_redirect_reason');
    if (reason) {
      setRedirectMessage(reason);
      sessionStorage.removeItem('auth_redirect_reason');
    }
  }, []);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(name, email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <img src="/logo.svg" alt="TerraCube IDEAS" />
          <strong>TerraCube IDEAS</strong>
        </div>

        <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
        <p>{mode === 'login' ? 'Sign in to launch the DGGS workspace.' : 'Register to start exploring DGGS layers.'}</p>

        {redirectMessage && (
          <div className="session-alert" style={{ background: 'rgba(59, 130, 246, 0.1)', borderColor: '#3b82f6', color: '#93c5fd' }}>
            {redirectMessage}
          </div>
        )}

        {mode === 'register' && (
          <div className="form-field">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
              required
            />
          </div>
        )}

        <div className="form-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@terracube.io"
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Minimum 8 characters"
            required
          />
        </div>

        {error && (
          <div className="session-alert">{error}</div>
        )}

        <button className="button-primary" type="submit" disabled={loading}>
          {loading ? 'Authenticating...' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button
          className="button-secondary"
          type="button"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
          style={{ marginTop: '0.75rem' }}
        >
          {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
};

export default LoginPage;
