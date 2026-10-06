import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';

import Sidebar from './components/Sidebar';
import Header from './components/Header';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProcessPage from './pages/ProcessPage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';

import { AuthProvider, useAuth } from './context/AuthContext';

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-muted)' }}>
        Verificando sesión...
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location }}
      />
    );
  }

  return children;
}

function AppLayout() {
  const location = useLocation();

  const getTitle = () => {
    if (location.pathname.startsWith('/dashboard')) {
      return 'Panel Principal';
    }

    if (location.pathname.startsWith('/process')) {
      return 'Nuevo Procesamiento de Examen';
    }

    if (location.pathname.startsWith('/history')) {
      return 'Historial de Exámenes';
    }

    if (location.pathname.startsWith('/results')) {
      return 'Resultados de Evaluación';
    }

    return 'OMRChecker Web Suite';
  };

  return (
    <div className="app-layout">
      <Sidebar />

      <div className="main-content">
        <Header title={getTitle()} />

        <Routes>
          <Route
            path="/dashboard"
            element={<DashboardPage />}
          />

          <Route
            path="/process"
            element={<ProcessPage />}
          />

          <Route
            path="/history"
            element={<HistoryPage />}
          />

          <Route
            path="/results/:jobId"
            element={<ResultsPage />}
          />

          <Route
            path="*"
            element={<Navigate to="/dashboard" replace />}
          />
        </Routes>
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/register"
        element={<RegisterPage />}
      />

      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}