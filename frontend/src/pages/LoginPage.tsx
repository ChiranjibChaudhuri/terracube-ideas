import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../lib/api';

const LoginPage = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
          <img src="/logo.svg" alt="TerraCube IDEAS logo" />
          <strong>TerraCube IDEAS</strong>
        </div>
        <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
        <p>{mode === 'login' ? 'Sign in to launch the DGGS workspace.' : 'Register to start exploring DGGS layers.'}</p>

        {mode === 'register' && (
          <div className="form-field">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="IDEAS Analyst"
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

        {error && <p style={{ color: '#b7412d' }}>{error}</p>}

        <button className="button-primary" type="submit" disabled={loading}>
          {loading ? 'Loading...' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button
          className="button-secondary"
          type="button"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          style={{ marginTop: '0.8rem' }}
        >
          {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
};

export default LoginPage;
