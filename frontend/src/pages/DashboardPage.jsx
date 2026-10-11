import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PlayCircle,
  ShieldCheck,
  CheckCircle2,
  Users,
  FileText,
  Activity,
  Layers,
  FileSpreadsheet,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function DashboardPage() {
  const { user } = useAuth();
  const [isHealthy, setIsHealthy] = useState(null);
  const [adminStats, setAdminStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [examsCount, setExamsCount] = useState(0);

  useEffect(() => {
    api.getHealth()
      .then(() => setIsHealthy(true))
      .catch(() => setIsHealthy(false));

    if (user?.role === 'admin') {
      setLoadingStats(true);
      api.getAdminStats()
        .then((stats) => setAdminStats(stats))
        .catch(() => {})
        .finally(() => setLoadingStats(false));
    } else {
      api.getExams()
        .then((exs) => setExamsCount(Array.isArray(exs) ? exs.length : 0))
        .catch(() => {});
    }
  }, [user]);

  const role = user?.role || 'usuario';

  return (
    <div className="page-container">
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
          {role === 'admin'
            ? 'Panel de Control del Administrador'
            : role === 'editor'
            ? 'Panel del Editor / Docente'
            : 'Panel del Evaluador'}
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          {role === 'admin'
            ? 'Supervisión global del sistema, estadísticas de uso, auditoría y control de accesos.'
            : role === 'editor'
            ? 'Configuración de evaluaciones OMR, pautas de respuestas y procesamiento de exámenes.'
            : 'Sube tus hojas de respuestas para exámenes autorizados y consulta tus calificaciones.'}
        </p>
      </div>

      {/* DASHBOARD PARA ROL ADMIN */}
      {role === 'admin' && adminStats && (
        <>
          <div className="grid-stats" style={{ marginBottom: '1.5rem' }}>
            <div className="card">
              <div className="stat-header">
                <span>Usuarios Registrados</span>
                <Users size={20} color="#6d28d9" />
              </div>
              <div className="stat-value" style={{ fontSize: '1.6rem', color: '#6d28d9' }}>
                {adminStats.users.total}
              </div>
              <div className="stat-subtext">
                {adminStats.users.by_role.editor || 0} Editores, {adminStats.users.by_role.usuario || 0} Usuarios ({adminStats.users.inactive || 0} inactivos)
              </div>
            </div>

            <div className="card">
              <div className="stat-header">
                <span>Exámenes Configurados</span>
                <FileText size={20} color="#2563eb" />
              </div>
              <div className="stat-value" style={{ fontSize: '1.6rem', color: '#2563eb' }}>
                {adminStats.exams.total}
              </div>
              <div className="stat-subtext">
                {adminStats.exams.active} activos en el sistema
              </div>
            </div>

            <div className="card">
              <div className="stat-header">
                <span>Cargas / Procesamientos</span>
                <Layers size={20} color="#059669" />
              </div>
              <div className="stat-value" style={{ fontSize: '1.6rem', color: '#059669' }}>
                {adminStats.jobs.total}
              </div>
              <div className="stat-subtext">
                {adminStats.jobs.completed} completados, {adminStats.jobs.with_errors} con alertas
              </div>
            </div>

            <div className="card">
              <div className="stat-header">
                <span>Hojas OMR Procesadas</span>
                <CheckCircle2 size={20} color="#0284c7" />
              </div>
              <div className="stat-value" style={{ fontSize: '1.6rem', color: '#0284c7' }}>
                {adminStats.sheets.total}
              </div>
              <div className="stat-subtext">
                {adminStats.sheets.success} exitosas, {adminStats.sheets.errors} errores
              </div>
            </div>
          </div>

          {/* Actividad Reciente del Sistema */}
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Activity size={18} color="#475569" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>Actividad Reciente del Sistema (Auditoría)</h3>
              </div>
              <Link to="/admin/users" className="btn btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>
                <span>Administrar Usuarios</span>
              </Link>
            </div>

            {adminStats.recent_activity && adminStats.recent_activity.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.825rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', background: '#f8fafc' }}>
                      <th style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>Fecha y Hora</th>
                      <th style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>Usuario</th>
                      <th style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>Rol</th>
                      <th style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>Acción</th>
                      <th style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminStats.recent_activity.map((log) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>
                          {new Date(log.timestamp).toLocaleString()}
                        </td>
                        <td style={{ padding: '0.6rem 0.75rem', fontWeight: 600 }}>
                          {log.user_name || log.user_email || 'Sistema'}
                        </td>
                        <td style={{ padding: '0.6rem 0.75rem' }}>
                          <span style={{ fontSize: '0.75rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: '#f1f5f9' }}>
                            {log.user_role || 'CLI'}
                          </span>
                        </td>
                        <td style={{ padding: '0.6rem 0.75rem', fontWeight: 600 }}>
                          {log.action}
                        </td>
                        <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-muted)' }}>
                          {log.ip_address || 'Local'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No hay registros recientes.</p>
            )}
          </div>
        </>
      )}

      {/* DASHBOARD PARA EDITOR Y USUARIO */}
      {role !== 'admin' && (
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
              <span>{role === 'editor' ? 'Mis Exámenes' : 'Exámenes Disponibles'}</span>
              <FileText size={20} color="#2563eb" />
            </div>
            <div className="stat-value" style={{ fontSize: '1.35rem' }}>
              {examsCount}
            </div>
            <div className="stat-subtext">
              {role === 'editor' ? 'Exámenes creados por ti' : 'Exámenes habilitados para procesar'}
            </div>
          </div>

          <div className="card">
            <div className="stat-header">
              <span>Plantilla OMR</span>
              <Layers size={20} color="#8b5cf6" />
            </div>
            <div className="stat-value" style={{ fontSize: '1.35rem' }}>
              Estandarizada
            </div>
            <div className="stat-subtext">Calibrada automáticamente por el sistema</div>
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
      )}

      {/* TARJETA DE ACCIONES RÁPIDAS */}
      <div className="card" style={{ padding: '2rem', textAlign: 'center', background: '#ffffff', marginTop: '1.5rem' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          {role === 'admin'
            ? 'Acciones de Administración'
            : role === 'editor'
            ? '¿Deseas configurar un nuevo examen o procesar hojas?'
            : '¿Listo para subir y evaluar tus hojas de respuestas?'}
        </h3>
        <p style={{ color: 'var(--text-muted)', maxWidth: '600px', margin: '0 auto 1.5rem auto', fontSize: '0.925rem' }}>
          {role === 'admin'
            ? 'Administra usuarios, revisa auditoría o inspecciona todos los exámenes y cargas del sistema.'
            : role === 'editor'
            ? 'Configura la clave de respuestas de un nuevo examen o procesa paquetes ZIP de hojas escaneadas.'
            : 'Selecciona un examen habilitado por tu profesor, sube tus archivos ZIP y descarga tus reportes en segundos.'}
        </p>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          {role === 'admin' ? (
            <>
              <Link to="/admin/users" className="btn btn-primary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <Users size={20} />
                <span>Gestionar Usuarios</span>
              </Link>
              <Link to="/exams" className="btn btn-secondary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <FileText size={20} />
                <span>Ver Todos los Exámenes</span>
              </Link>
              <Link to="/history" className="btn btn-secondary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <span>Historial Global</span>
              </Link>
            </>
          ) : role === 'editor' ? (
            <>
              <Link to="/exams" className="btn btn-primary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <FileText size={20} />
                <span>Configurar Exámenes</span>
              </Link>
              <Link to="/process" className="btn btn-secondary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <PlayCircle size={20} />
                <span>Procesar Hojas ZIP</span>
              </Link>
            </>
          ) : (
            <>
              <Link to="/exams" className="btn btn-primary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <FileText size={20} />
                <span>Ver Exámenes Habilitados</span>
              </Link>
              <Link to="/process" className="btn btn-secondary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <PlayCircle size={20} />
                <span>Subir Hojas (ZIP)</span>
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
