import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlayCircle, ShieldCheck, CheckCircle2, Clock, FileSpreadsheet, Layers } from 'lucide-react';
import { api } from '../services/api';

export default function DashboardPage() {
  const [isHealthy, setIsHealthy] = useState(null);

  useEffect(() => {
    api.getHealth()
      .then(() => setIsHealthy(true))
      .catch(() => setIsHealthy(false));
  }, []);

  return (
    <div className="page-container">
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
          Sistema de Calificación OMR
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          Corrección automatizada de hojas de respuestas mediante visión por computadora nativa (OMRChecker).
        </p>
      </div>

      <div className="grid-stats">
        <div className="card">
          <div className="stat-header">
            <span>Estado del Motor OMR</span>
            <ShieldCheck size={20} color={isHealthy ? '#10b981' : '#ef4444'} />
          </div>
          <div className="stat-value" style={{ fontSize: '1.35rem', color: isHealthy ? '#10b981' : '#ef4444' }}>
            {isHealthy ? 'Operativo y Conectado' : isHealthy === false ? 'Desconectado' : 'Comprobando...'}
          </div>
          <div className="stat-subtext">OMRChecker Core + FastAPI Backend</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Plantilla OMR</span>
            <Layers size={20} color="#2563eb" />
          </div>
          <div className="stat-value" style={{ fontSize: '1.35rem' }}>
            Estandarizada
          </div>
          <div className="stat-subtext">Calibrada automáticamente por el sistema</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Evaluación</span>
            <CheckCircle2 size={20} color="#8b5cf6" />
          </div>
          <div className="stat-value" style={{ fontSize: '1.35rem' }}>
            Clave Dinámica
          </div>
          <div className="stat-subtext">Generada en frontend a partir de tu pauta</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Exportaciones</span>
            <FileSpreadsheet size={20} color="#059669" />
          </div>
          <div className="stat-value" style={{ fontSize: '1.35rem' }}>
            CSV / Excel
          </div>
          <div className="stat-subtext">Resultados agregados y detalle por pregunta</div>
        </div>
      </div>

      <div className="card" style={{ padding: '2rem', textAlign: 'center', background: '#ffffff', marginTop: '1.5rem' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          ¿Listo para procesar un paquete de exámenes?
        </h3>
        <p style={{ color: 'var(--text-muted)', maxWidth: '600px', margin: '0 auto 1.5rem auto', fontSize: '0.925rem' }}>
          Sube tu archivo ZIP con las hojas de examen escaneadas o fotografiadas, define la clave de respuestas correcta y obtén los resultados calificados al instante.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/process" className="btn btn-primary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
            <PlayCircle size={20} />
            <span>Iniciar Nuevo Procesamiento</span>
          </Link>
          <Link to="/history" className="btn btn-secondary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
            <span>Consultar Historial</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

