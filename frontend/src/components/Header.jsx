import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { BookOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Header({ title }) {
  const [isHealthy, setIsHealthy] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    let mounted = true;
    api.getHealth()
      .then(() => {
        if (mounted) setIsHealthy(true);
      })
      .catch(() => {
        if (mounted) setIsHealthy(false);
      });
    return () => { mounted = false; };
  }, []);

  return (
    <header className="header">
      <h1 className="header-title">{title}</h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="btn btn-secondary"
          style={{ padding: '0.4rem 0.85rem', fontSize: '0.825rem' }}
        >
          <BookOpen size={16} />
          <span>Swagger API Docs</span>
        </a>

        <div className="header-status">
          <div
            className="status-dot"
            style={{ backgroundColor: isHealthy ? '#10b981' : isHealthy === false ? '#ef4444' : '#f59e0b' }}
          />
          <span>{isHealthy ? 'FastAPI Conectada' : isHealthy === false ? 'API Desconectada' : 'Verificando...'}</span>
        </div>

        {user && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              paddingLeft: '0.75rem',
              borderLeft: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.2 }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
                {user.nombre}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {user.correo}
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
