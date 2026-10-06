import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  History,
  FileText,
  Calendar,
  Eye,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RefreshCw,
  Search,
  PlayCircle,
} from 'lucide-react';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function HistoryPage() {
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const loadHistory = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getHistory();
      setExams(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Error al obtener el historial de exámenes.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const filteredExams = exams.filter((exam) => {
    const name = (exam.exam_name || '').toLowerCase();
    const id = (exam.job_id || '').toLowerCase();
    const query = searchTerm.toLowerCase();
    return name.includes(query) || id.includes(query);
  });

  return (
    <div className="page-container">
      {/* Encabezado */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
            Historial de Exámenes
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Consulta y gestiona las evaluaciones y exámenes procesados con tu cuenta.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={loadHistory}
            className="btn btn-secondary"
            title="Recargar historial"
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <RefreshCw size={16} />
            <span>Actualizar</span>
          </button>
          <Link to="/process" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <PlayCircle size={18} />
            <span>Nuevo Examen</span>
          </Link>
        </div>
      </div>

      {error && (
        <div style={{
          backgroundColor: 'var(--danger-light)',
          color: 'var(--danger)',
          padding: '1rem',
          borderRadius: 'var(--radius-md)',
          marginBottom: '1.5rem',
          border: '1px solid #fecaca',
        }}>
          {error}
        </div>
      )}

      {/* Barra de búsqueda */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Buscar examen por nombre o ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-input"
            style={{ width: '100%', border: 'none', padding: '0.25rem 0.5rem', fontSize: '0.95rem' }}
          />
        </div>
      </div>

      {/* Contenido principal */}
      {loading ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <RefreshCw
            size={36}
            style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)', margin: '0 auto 1rem auto' }}
          />
          <h4 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Cargando historial de exámenes...</h4>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Recuperando registros del servidor.</p>
          <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : exams.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <History size={48} color="#94a3b8" style={{ margin: '0 auto 1rem auto' }} />
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            No tienes exámenes procesados aún
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem', maxWidth: '460px', margin: '0 auto 1.5rem auto' }}>
            Sube tu primer archivo ZIP con hojas OMR y define la pauta de corrección para ver tus resultados aquí.
          </p>
          <Link to="/process" className="btn btn-primary" style={{ display: 'inline-flex', padding: '0.75rem 1.5rem' }}>
            <PlayCircle size={18} />
            <span>Procesar Mi Primer Examen</span>
          </Link>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '0.85rem 1.25rem', textAlign: 'left', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Nombre del examen
                  </th>
                  <th style={{ padding: '0.85rem 1rem', textAlign: 'left', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Fecha
                  </th>
                  <th style={{ padding: '0.85rem 1rem', textAlign: 'left', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Usuario
                  </th>
                  <th style={{ padding: '0.85rem 1rem', textAlign: 'center', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Estado
                  </th>
                  <th style={{ padding: '0.85rem 1rem', textAlign: 'center', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Hojas / Evaluadas
                  </th>
                  <th style={{ padding: '0.85rem 1rem', textAlign: 'center', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Promedio
                  </th>
                  <th style={{ padding: '0.85rem 1.25rem', textAlign: 'right', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Acción
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredExams.map((job) => {
                  const hasErrors = (job.error_count && job.error_count > 0) || job.status === 'completed_with_errors';
                  return (
                    <tr key={job.job_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '1rem 1.25rem' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.95rem' }}>
                          {job.exam_name || 'Examen OMR'}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace', marginTop: '0.2rem' }}>
                          ID: {job.job_id}
                        </div>
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.875rem', color: 'var(--text-main)', whiteSpace: 'nowrap' }}>
                        {formatDate(job.created_at)}
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.875rem', color: 'var(--text-main)' }}>
                        <div style={{ fontWeight: 500 }}>{job.user_name || 'Profesor'}</div>
                        {job.user_email && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{job.user_email}</div>
                        )}
                      </td>
                      <td style={{ padding: '1rem', textAlign: 'center' }}>
                        {hasErrors ? (
                          <span
                            className="badge"
                            style={{
                              background: '#fef2f2',
                              color: '#dc2626',
                              border: '1px solid #fecaca',
                              fontWeight: 600,
                              padding: '0.3rem 0.6rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                            }}
                          >
                            <AlertTriangle size={13} />
                            <span>⚠ Procesado con errores</span>
                          </span>
                        ) : job.status === 'completed' ? (
                          <span
                            className="badge"
                            style={{
                              background: '#ecfdf5',
                              color: '#059669',
                              border: '1px solid #a7f3d0',
                              fontWeight: 600,
                              padding: '0.3rem 0.6rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                            }}
                          >
                            <CheckCircle2 size={13} />
                            <span>Procesado correctamente</span>
                          </span>
                        ) : (
                          <span className="badge badge-warning">
                            {job.status === 'processing' ? 'En proceso' : job.status || 'Pendiente'}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '1rem', textAlign: 'center', fontSize: '0.9rem' }}>
                        <strong>{job.total_files}</strong> {job.total_files === 1 ? 'hoja' : 'hojas'}
                        {job.zip_count && job.zip_count > 1 && (
                          <div style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 600 }}>
                            {job.zip_count} archivos ZIP
                          </div>
                        )}
                        {job.question_count && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {job.question_count} preguntas
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '1rem', textAlign: 'center' }}>
                        <span style={{ fontWeight: 700, color: job.average_score > 0 ? '#10b981' : 'inherit' }}>
                          {job.average_score.toFixed(2)}
                        </span>
                      </td>
                      <td style={{ padding: '1rem 1.25rem', textAlign: 'right' }}>
                        <Link
                          to={`/results/${job.job_id}`}
                          className="btn btn-secondary"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.85rem', fontSize: '0.85rem' }}
                        >
                          <Eye size={15} />
                          <span>Ver Detalle</span>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
