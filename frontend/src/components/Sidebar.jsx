import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  PlayCircle,
  History,
  CheckCircle2,
  ShieldCheck,
  LogOut,
  Users,
  FileText,
  Shield,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const role = user?.role || 'usuario';

  let roleLabel = 'Usuario';
  let roleBadgeBg = '#f1f5f9';
  let roleBadgeColor = '#475569';

  if (role === 'admin') {
    roleLabel = 'Administrador';
    roleBadgeBg = '#ede9fe';
    roleBadgeColor = '#6d28d9';
  } else if (role === 'editor') {
    roleLabel = 'Editor / Docente';
    roleBadgeBg = '#e0f2fe';
    roleBadgeColor = '#0369a1';
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <CheckCircle2 size={22} />
        </div>
        <div>
          <div className="sidebar-title">OMRChecker</div>
          <div className="sidebar-subtitle">Web Suite v1.0</div>
        </div>
      </div>

      {user && (
        <div style={{ padding: '0.5rem 1rem 1rem 1rem', borderBottom: '1px solid var(--border)', marginBottom: '0.5rem' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {user.nombre}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.3rem' }}>
            <span
              style={{
                padding: '0.15rem 0.5rem',
                borderRadius: '999px',
                fontSize: '0.7rem',
                fontWeight: 600,
                background: roleBadgeBg,
                color: roleBadgeColor,
              }}
            >
              {roleLabel}
            </span>
          </div>
        </div>
      )}

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        {role === 'admin' && (
          <NavLink
            to="/admin/users"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Users size={18} />
            <span>Usuarios</span>
          </NavLink>
        )}

        <NavLink
          to="/exams"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <FileText size={18} />
          <span>
            {role === 'admin'
              ? 'Exámenes'
              : 'Mis Exámenes'}
          </span>
        </NavLink>

        <NavLink
          to="/process"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <PlayCircle size={18} />
          <span>{role === 'usuario' ? 'Subir y Procesar' : 'Nuevo Procesamiento'}</span>
        </NavLink>

        <NavLink
          to="/history"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <History size={18} />
          <span>
            {role === 'admin'
              ? 'Historial Global'
              : role === 'editor'
              ? 'Historial de Cargas'
              : 'Mi Historial'}
          </span>
        </NavLink>
      </nav>

      <div style={{ padding: '0 1rem', marginTop: 'auto', marginBottom: '1rem' }}>
        <button
          type="button"
          onClick={handleLogout}
          className="nav-item"
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            color: '#dc2626',
            background: '#fef2f2',
            border: '1px solid #fee2e2',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.9rem',
            textAlign: 'left',
          }}
          title="Cerrar sesión y salir"
        >
          <LogOut size={18} color="#dc2626" />
          <span>Cerrar sesión</span>
        </button>
      </div>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <ShieldCheck size={16} color="#10b981" />
          <span style={{ fontWeight: 600, color: '#0f172a' }}>Motor Nativo</span>
        </div>
        <div>OMRChecker Core (src/)</div>
      </div>
    </aside>
  );
}
