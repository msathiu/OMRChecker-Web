import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate, Link } from 'react-router-dom';
import { CheckCircle2, LockKeyhole, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [correo, setCorreo] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const registeredSuccess = location.state?.registered;

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!correo.trim()) {
      setError('Por favor ingresa tu correo institucional.');
      return;
    }
    if (!clave) {
      setError('Por favor ingresa tu clave.');
      return;
    }

    setIsLoading(true);

    const result = await login(correo.trim(), clave);

    if (result.success) {
      const destination = location.state?.from?.pathname || '/dashboard';
      navigate(destination, { replace: true });
    } else {
      setError(result.message);
    }

    setIsLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: '440px' }}>
        <div className="login-brand">
          <div className="login-logo">
            <CheckCircle2 size={34} />
          </div>
          <h1>OMRChecker</h1>
          <p>Web Suite</p>
        </div>

        <div className="login-header">
          <h2>Iniciar sesión</h2>
          <p>Ingresa tu correo institucional y clave para acceder al sistema.</p>
        </div>

        {registeredSuccess && !error && (
          <div
            style={{
              backgroundColor: '#ecfdf5',
              color: '#065f46',
              border: '1px solid #a7f3d0',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1rem',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <CheckCircle2 size={18} color="#10b981" />
            <span>¡Cuenta registrada con éxito! Ya puedes iniciar sesión.</span>
          </div>
        )}

        {error && (
          <div
            className="login-error"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="correo">Correo institucional</label>
            <div className="input-with-icon">
              <Mail size={18} />
              <input
                id="correo"
                type="email"
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
                placeholder="ejemplo@institucion.edu"
                autoComplete="email"
                disabled={isLoading}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="clave">Clave</label>
            <div className="input-with-icon">
              <LockKeyhole size={18} />
              <input
                id="clave"
                type="password"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                placeholder="Ingresa tu clave"
                autoComplete="current-password"
                disabled={isLoading}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary login-button"
            style={{ width: '100%', marginTop: '0.5rem' }}
            disabled={isLoading}
          >
            {isLoading ? 'Ingresando...' : 'Iniciar sesión'}
          </button>
        </form>

        <div style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          ¿No tienes una cuenta?{' '}
          <Link
            to="/register"
            style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}
          >
            Regístrate aquí
          </Link>
        </div>
      </div>
    </div>
  );
}