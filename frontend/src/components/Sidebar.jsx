import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, PlayCircle, History, CheckCircle2, ShieldCheck, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

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

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/process"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <PlayCircle size={18} />
          <span>Nuevo Procesamiento</span>
        </NavLink>

        <NavLink
          to="/history"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <History size={18} />
          <span>Historial de Exámenes</span>
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
