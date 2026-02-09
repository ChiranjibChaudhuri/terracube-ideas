import { Navigate, Route, Routes } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import Workbench from './pages/Workbench';
import HighVibe from './pages/HighVibe';
import ErrorBoundary from './components/ErrorBoundary';

const RequireAuth = ({ children }: { children: JSX.Element }) => {
  const token = localStorage.getItem('ideas_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

const App = () => {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/high-vibes"
          element={
            <RequireAuth>
              <HighVibe />
            </RequireAuth>
          }
        />
        <Route
          path="/workbench"
          element={
            <RequireAuth>
              <Workbench />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
};

export default App;
