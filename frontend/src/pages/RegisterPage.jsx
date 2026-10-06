import React, { useState } from 'react';
import { Navigate, useNavigate, Link } from 'react-router-dom';
import { CheckCircle2, LockKeyhole, Mail, User, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RegisterPage() {
  const { register, login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [nombre, setNombre] = useState('');
  const [correo, setCorreo] = useState('');
  const [clave, setClave] = useState('');
  const [confirmacionClave, setConfirmacionClave] = useState('');

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleInputChange = (setter) => (e) => {
    setter(e.target.value);
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validaciones de cliente
    if (!nombre.trim()) {
      setError('El campo Nombre es obligatorio.');
      return;
    }
    const cleanEmail = correo.trim().toLowerCase();
    if (!cleanEmail || !EMAIL_REGEX.test(cleanEmail)) {
      setError('El correo electrónico no tiene un formato válido.');
      return;
    }
    if (!clave) {
      setError('El campo Clave es obligatorio.');
      return;
    }
    if (!confirmacionClave) {
      setError('El campo Confirmación de clave es obligatorio.');
      return;
    }
    if (clave !== confirmacionClave) {
      setError('La clave y la confirmación no coinciden.');
      return;
    }

    setIsLoading(true);

    const result = await register({
      nombre: nombre.trim(),
      correo: cleanEmail,
      clave,
      confirmacion_clave: confirmacionClave,
    });

    if (result.success) {
      // Iniciar sesión automáticamente tras el registro exitoso
      const loginResult = await login(cleanEmail, clave);
      if (loginResult.success) {
        navigate('/dashboard', { replace: true });
      } else {
        navigate('/login', { state: { registered: true }, replace: true });
      }
    } else {
      const msg = (result.message && typeof result.message === 'string' && result.message !== '[object Object]')
        ? result.message
        : 'Error al registrar la cuenta.';
      setError(msg);
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
          <h2>Registro de Usuario</h2>
          <p>Crea tu cuenta institucional para acceder al sistema.</p>
        </div>

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

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="nombre">Nombre</label>
            <div className="input-with-icon">
              <User size={18} />
              <input
                id="nombre"
                type="text"
                value={nombre}
                onChange={handleInputChange(setNombre)}
                placeholder="Nombre completo"
                autoComplete="name"
                disabled={isLoading}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="correo">Correo institucional</label>
            <div className="input-with-icon">
              <Mail size={18} />
              <input
                id="correo"
                type="email"
                value={correo}
                onChange={handleInputChange(setCorreo)}
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
                onChange={handleInputChange(setClave)}
                placeholder="Crea una contraseña segura"
                autoComplete="new-password"
                disabled={isLoading}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="confirmacionClave">Confirmación de clave</label>
            <div className="input-with-icon">
              <LockKeyhole size={18} />
              <input
                id="confirmacionClave"
                type="password"
                value={confirmacionClave}
                onChange={handleInputChange(setConfirmacionClave)}
                placeholder="Repite la contraseña"
                autoComplete="new-password"
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
            {isLoading ? 'Registrando...' : 'Registrar cuenta'}
          </button>
        </form>

        <div style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          ¿Ya tienes una cuenta?{' '}
          <Link
            to="/login"
            style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}
          >
            Inicia sesión aquí
          </Link>
        </div>
      </div>
    </div>
  );
}
