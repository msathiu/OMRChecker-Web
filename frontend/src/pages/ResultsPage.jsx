import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Download,
  FileSpreadsheet,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ArrowLeft,
  Eye,
  X,
  RefreshCw,
  User,
  Calendar,
  Layers,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Upload,
  FileArchive,
} from 'lucide-react';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function ResultsPage() {
  const { jobId } = useParams();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [expandedSheetIdx, setExpandedSheetIdx] = useState(null);

  // Estados para recarga selectiva de ZIP corregido
  const [showRetryModal, setShowRetryModal] = useState(false);
  const [retryFile, setRetryFile] = useState(null);
  const [retryLoading, setRetryLoading] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [retrySuccess, setRetrySuccess] = useState('');

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.getJobResults(jobId)
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Error al cargar los resultados del trabajo.');
          setLoading(false);
        }
      });

    return () => { mounted = false; };
  }, [jobId]);

  const handleRetrySubmit = async (e) => {
    e.preventDefault();
    if (!retryFile) {
      setRetryError('Por favor selecciona un archivo ZIP con las hojas corregidas.');
      return;
    }
    setRetryLoading(true);
    setRetryError('');
    try {
      const formData = new FormData();
      formData.append('zip_file', retryFile);
      const updatedData = await api.retryJob(jobId, formData);
      setData(updatedData);
      setShowRetryModal(false);
      setRetryFile(null);
      setRetrySuccess('El examen fue actualizado exitosamente con las hojas corregidas.');
    } catch (err) {
      setRetryError(err.message || 'Error al procesar el archivo ZIP corregido.');
    } finally {
      setRetryLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Fecha no registrada';
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

  if (loading) {
    return (
      <div className="page-container" style={{ textAlign: 'center', padding: '5rem 2rem' }}>
        <RefreshCw size={36} className="spin-icon" style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)', margin: '0 auto 1rem auto' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Cargando información del examen...</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Recuperando hojas procesadas y calificaciones desde el servidor.</p>
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-container" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
        <XCircle size={48} color="var(--danger)" style={{ margin: '0 auto 1rem auto' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--danger)', marginBottom: '0.5rem' }}>
          No se pudo consultar el examen
        </h3>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', maxWidth: '500px', margin: '0 auto 1.5rem auto' }}>
          {error || 'El examen no existe o aún no ha finalizado su procesamiento.'}
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <Link to="/history" className="btn btn-secondary">
            <span>Ir al Historial</span>
          </Link>
          <Link to="/process" className="btn btn-primary">
            <span>Nuevo Examen</span>
          </Link>
        </div>
      </div>
    );
  }

  const results = data.results || [];
  const firstAudits = (results.length > 0 && results[0].audits) ? results[0].audits : [];
  const questionCount = data.question_count || firstAudits.length || 0;
  const hasErrors = (data.error_count && data.error_count > 0) || data.status === 'completed_with_errors' || results.some(r => r.status === 'ERROR' || r.status === 'failed');

  return (
    <div className="page-container">
      {/* DETALLE DEL EXAMEN: Encabezado y acciones de exportación */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
            <Link to="/history" className="btn btn-secondary" style={{ padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}>
              <ArrowLeft size={16} />
              <span>Historial</span>
            </Link>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              {data.exam_name || 'Examen OMR'}
            </h2>
            {hasErrors ? (
              <span
                className="badge"
                style={{
                  background: '#fef2f2',
                  color: '#dc2626',
                  border: '1px solid #fecaca',
                  fontWeight: 600,
                  padding: '0.35rem 0.65rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                <AlertTriangle size={14} />
                <span>⚠ Procesado con errores</span>
              </span>
            ) : (
              <span
                className="badge badge-success"
                style={{
                  background: '#ecfdf5',
                  color: '#059669',
                  border: '1px solid #a7f3d0',
                  fontWeight: 600,
                  padding: '0.35rem 0.65rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                <CheckCircle2 size={14} />
                <span>Procesado correctamente</span>
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap', color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Calendar size={15} />
              <span>{formatDate(data.created_at)}</span>
            </div>
            {data.user_name && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <User size={15} />
                <span>{data.user_name} ({data.user_email || 'Profesor'})</span>
              </div>
            )}
            <div style={{ fontFamily: 'monospace' }}>
              ID: {jobId}
            </div>
          </div>
        </div>

        {/* Acciones de recarga y descarga */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => {
              setRetryError('');
              setRetryFile(null);
              setShowRetryModal(true);
            }}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#b45309', borderColor: '#fde68a', background: '#fffbeb' }}
            title="Subir un archivo ZIP con hojas corregidas"
          >
            <Upload size={16} color="#d97706" />
            <span>Volver a cargar ZIP corregido</span>
          </button>

          <button
            onClick={() => api.downloadFile(api.getExportCsvUrl(jobId), `omr_${(data.exam_name || 'resultados').replace(/\s+/g, '_')}_${jobId.slice(0, 6)}.csv`)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <FileText size={18} color="#0284c7" />
            <span>Descargar CSV</span>
          </button>

          <button
            onClick={() => api.downloadFile(api.getExportExcelUrl(jobId), `omr_${(data.exam_name || 'resultados').replace(/\s+/g, '_')}_${jobId.slice(0, 6)}.xlsx`)}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#059669', borderColor: '#059669' }}
          >
            <FileSpreadsheet size={18} />
            <span>Descargar Excel</span>
          </button>
        </div>
      </div>

      {/* Banner de éxito tras recarga */}
      {retrySuccess && (
        <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46', borderRadius: 'var(--radius-md)', padding: '0.85rem 1.25rem', marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
            <CheckCircle2 size={18} color="#059669" />
            <span>{retrySuccess}</span>
          </div>
          <button
            onClick={() => setRetrySuccess('')}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#065f46', padding: '0.2rem' }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Banner de alerta si hay errores OMR */}
      {hasErrors && (
        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 'var(--radius-md)', padding: '1rem 1.25rem', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <AlertTriangle size={22} color="#d97706" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#92400e' }}>
                Atención: Se detectaron {data.error_count || results.filter(r => r.status === 'ERROR' || r.status === 'failed').length} hoja(s) con error de procesamiento
              </div>
              <div style={{ fontSize: '0.85rem', color: '#b45309', marginTop: '0.25rem' }}>
                Posible causa: los marcadores de alineamiento no fueron detectados, o la imagen está borrosa, recortada o inclinada fuera del área esperada.
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setRetryError('');
              setRetryFile(null);
              setShowRetryModal(true);
            }}
            className="btn btn-primary"
            style={{ background: '#d97706', borderColor: '#d97706', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', whiteSpace: 'nowrap' }}
          >
            <Upload size={16} />
            <span>Volver a cargar ZIP corregido</span>
          </button>
        </div>
      )}

      {/* RESUMEN DE ARCHIVOS ZIP PROCESADOS */}
      {data.zips_summary && data.zips_summary.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <FileArchive size={18} color="var(--primary)" />
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
              Archivos ZIP Procesados ({data.zips_summary.length})
            </h4>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.65rem' }}>
            {data.zips_summary.map((zip, idx) => {
              const isOk = zip.status === 'COMPLETED';
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.55rem 0.85rem',
                    backgroundColor: isOk ? '#f0fdf4' : '#fef2f2',
                    border: `1px solid ${isOk ? '#bbf7d0' : '#fecaca'}`,
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                    {isOk ? <CheckCircle2 size={16} color="#16a34a" /> : <XCircle size={16} color="#dc2626" />}
                    <span style={{ fontWeight: 600, color: isOk ? '#166534' : '#991b1b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={zip.filename}>
                      {zip.filename}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                    {isOk ? (
                      <span style={{ fontSize: '0.75rem', color: '#166534', fontWeight: 600 }}>
                        {zip.total_sheets} hojas (OK)
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 600 }} title={zip.error_message || 'Error en archivo'}>
                        ERROR
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tarjetas de estadísticas agregadas */}
      <div className="grid-stats" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="stat-header">
            <span>Hojas Procesadas</span>
            <CheckCircle2 size={18} color="#2563eb" />
          </div>
          <div className="stat-value">{data.total_files}</div>
          <div className="stat-subtext">{data.success_count} evaluadas correctamente</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Promedio de Puntos</span>
            <span style={{ fontWeight: 600, color: '#10b981' }}>Media</span>
          </div>
          <div className="stat-value">{data.average_score.toFixed(2)}</div>
          <div className="stat-subtext">Puntaje promedio obtenido</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Puntaje Máximo</span>
            <span style={{ fontWeight: 600, color: '#059669' }}>Top</span>
          </div>
          <div className="stat-value">{data.highest_score.toFixed(2)}</div>
          <div className="stat-subtext">Calificación más alta</div>
        </div>

        <div className="card">
          <div className="stat-header">
            <span>Preguntas / Ítems</span>
            <Layers size={18} color="#6366f1" />
          </div>
          <div className="stat-value">{questionCount}</div>
          <div className="stat-subtext">Preguntas por hoja OMR</div>
        </div>
      </div>

      {/* CONFIGURACIÓN UTILIZADA (Pauta de respuestas y puntos asignados) */}
      {firstAudits.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1.25rem' }}>
          <div
            onClick={() => setShowConfig(!showConfig)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={18} color="var(--primary)" />
              <h4 style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-main)', margin: 0 }}>
                Configuración y Clave de Respuestas Utilizada ({questionCount} preguntas)
              </h4>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              <span>{showConfig ? 'Ocultar' : 'Ver Clave'}</span>
              {showConfig ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>

          {showConfig && (
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                Respuestas correctas configuradas para la corrección automática:
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', maxHeight: '180px', overflowY: 'auto' }}>
                {firstAudits.map((a, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: '0.8rem',
                      padding: '0.25rem 0.6rem',
                      borderRadius: '4px',
                      background: '#eff6ff',
                      color: '#1e40af',
                      fontWeight: 600,
                      border: '1px solid #bfdbfe',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <span>{a.question}:</span>
                    <strong style={{ color: '#2563eb' }}>{a.allowed_answers || '-'}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tabla detallada de estudiantes evaluados */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>Resultados por Estudiante / Hoja</h3>
            <div style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>{results.length} hoja(s) en este examen</div>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                <th style={{ padding: '0.75rem 1.25rem' }}>Archivo</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>ID / Cédula</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'right' }}>Puntuación</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'center' }}>Correctas</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'center' }}>Incorrectas</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'center' }}>Sin Responder</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'center' }}>Estado</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'center' }}>Hoja Marcada</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => {
                const isError = r.status === 'ERROR' || r.status === 'failed';
                const roll = isError ? '—' : (r.responses?.Roll || r.responses?.roll || r.responses?.id || '—');
                const markedImgName = isError ? r.file_id : `marked_${r.file_id}`;
                const imgUrl = isError
                  ? (r.original_image_url || api.getOriginalImageUrl(jobId, r.file_id))
                  : (r.processed_image_url || api.getImageUrl(jobId, markedImgName));
                const possibleCauseText = r.possible_cause || 'Posible causa: los marcadores de alineamiento no fueron detectados, o la imagen está borrosa, recortada o inclinada fuera del área esperada.';
                const isExpanded = expandedSheetIdx === idx;

                return (
                  <React.Fragment key={idx}>
                    <tr style={{ borderBottom: isError ? 'none' : '1px solid var(--border)', background: isError ? '#fff8f8' : isExpanded ? '#f8fafc' : 'transparent', transition: 'background 0.15s ease' }}>
                      <td style={{ padding: '0.85rem 1.25rem', fontWeight: 500, color: 'var(--text-main)' }}>
                        {r.original_name}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', fontFamily: 'monospace', fontWeight: 600 }}>
                        {roll}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'right', fontWeight: 700 }}>
                        {isError ? (
                          <span style={{ color: '#dc2626', fontWeight: 700 }}>ERROR</span>
                        ) : (
                          <>
                            <span style={{ color: r.score > 0 ? '#059669' : r.score < 0 ? '#dc2626' : 'inherit' }}>
                              {r.score.toFixed(2)}
                            </span>
                            {r.max_score && (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                                {' '}/ {r.max_score}
                              </span>
                            )}
                            {r.percentage !== null && r.percentage !== undefined && (
                              <span style={{ fontSize: '0.775rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '0.35rem' }}>
                                ({r.percentage}%)
                              </span>
                            )}
                          </>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'center' }}>
                        {isError ? (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        ) : (
                          <span style={{ color: '#059669', fontWeight: 600, background: '#ecfdf5', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                            {r.correctas || 0}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'center' }}>
                        {isError ? (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        ) : (
                          <span style={{ color: '#dc2626', fontWeight: 600, background: '#fef2f2', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                            {r.incorrectas || 0}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'center' }}>
                        {isError ? (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        ) : (
                          <span style={{ color: '#d97706', fontWeight: 600, background: '#fffbeb', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                            {r.sin_responder || 0}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'center' }}>
                        <StatusBadge status={r.status} multiMarked={r.multi_marked} />
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'center' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          <button
                            onClick={() => setSelectedImage({
                              name: isError ? r.original_name : markedImgName,
                              url: imgUrl,
                              student: isError ? r.original_name : roll,
                              isError,
                              errorMessage: r.error_message,
                              possibleCause: possibleCauseText,
                            })}
                            className="btn btn-secondary"
                            style={{
                              padding: '0.3rem 0.65rem',
                              fontSize: '0.8rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              color: isError ? '#dc2626' : 'inherit',
                              borderColor: isError ? '#fca5a5' : 'var(--border)',
                            }}
                            title={isError ? 'Ver imagen original para verificar el fallo' : 'Ver hoja procesada con recuadros y detecciones OMR'}
                          >
                            <Eye size={14} />
                            <span>{isError ? 'Ver Hoja Original' : 'Ver Hoja Calificada'}</span>
                          </button>

                          {!isError && r.audits && r.audits.length > 0 && (
                            <button
                              onClick={() => setExpandedSheetIdx(isExpanded ? null : idx)}
                              className="btn btn-secondary"
                              style={{
                                padding: '0.3rem 0.5rem',
                                fontSize: '0.775rem',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                                borderColor: isExpanded ? 'var(--primary)' : 'var(--border)',
                                color: isExpanded ? 'var(--primary)' : 'var(--text-main)',
                              }}
                              title="Ver desglose detallado de cada pregunta"
                            >
                              <span>Detalle</span>
                              {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Desglose desplegable de preguntas del estudiante */}
                    {isExpanded && !isError && r.audits && r.audits.length > 0 && (
                      <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                        <td colSpan={8} style={{ padding: '0.85rem 1.25rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
                              Desglose de respuestas detectadas — ID: {roll} ({r.original_name})
                            </span>
                            <span style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
                              {r.audits.length} preguntas evaluadas
                            </span>
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', maxHeight: '180px', overflowY: 'auto' }}>
                            {r.audits.map((a, aIdx) => {
                              const isCorrect = a.verdict?.toLowerCase().startsWith('correct');
                              const isMulti = a.verdict === 'MULTIMARCADA' || a.marked === 'MULTIMARCADA';
                              const isIncompleta = a.verdict === 'INCOMPLETA' || a.marked === 'INCOMPLETA';
                              const isSinResponder = a.verdict === 'SIN RESPONDER' || a.marked === 'SIN RESPONDER' || a.verdict?.toLowerCase().startsWith('unmarked');

                              let bg = '#fee2e2';
                              let border = '#fca5a5';
                              let textColor = '#dc2626';
                              let label = a.marked || '-';

                              if (isCorrect) {
                                bg = '#dcfce7';
                                border = '#86efac';
                                textColor = '#16a34a';
                              } else if (isMulti) {
                                bg = '#fef3c7';
                                border = '#fcd34d';
                                textColor = '#d97706';
                                label = 'MULTIMARCADA';
                              } else if (isIncompleta) {
                                bg = '#f3e8ff';
                                border = '#d8b4fe';
                                textColor = '#9333ea';
                                label = 'INCOMPLETA';
                              } else if (isSinResponder) {
                                bg = '#f1f5f9';
                                border = '#cbd5e1';
                                textColor = '#64748b';
                                label = 'SIN RESPONDER';
                              }

                              return (
                                <span
                                  key={aIdx}
                                  style={{
                                    fontSize: '0.75rem',
                                    padding: '0.2rem 0.5rem',
                                    borderRadius: '4px',
                                    background: bg,
                                    border: `1px solid ${border}`,
                                    color: textColor,
                                    fontWeight: 600,
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.3rem',
                                  }}
                                  title={`Pregunta ${a.question}: Marcada = ${a.marked} | Clave = ${a.allowed_answers} | Resultado = ${a.verdict} | Delta = ${a.delta}`}
                                >
                                  <span>{a.question}:</span>
                                  <strong>{label}</strong>
                                  {!isCorrect && a.allowed_answers && (
                                    <span style={{ fontSize: '0.7rem', opacity: 0.75 }}>({a.allowed_answers})</span>
                                  )}
                                </span>
                              );
                            })}
                          </div>
                        </td>
                      </tr>
                    )}

                    {isError && (
                      <tr style={{ background: '#fef2f2', borderBottom: '1px solid #fee2e2' }}>
                        <td colSpan={8} style={{ padding: '0.65rem 1.25rem', fontSize: '0.825rem', color: '#991b1b' }}>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                            <AlertTriangle size={15} color="#dc2626" style={{ flexShrink: 0, marginTop: '2px' }} />
                            <div>
                              <strong>Estado de la hoja: ERROR.</strong>{' '}
                              <span>{r.error_message ? `${r.error_message}. ` : ''}</span>
                              <span style={{ color: '#b91c1c' }}>
                                {possibleCauseText}
                              </span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal para visualizar hoja OMR procesada o con error */}
      {selectedImage && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 50,
          padding: '1.5rem',
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: 'var(--radius-lg)',
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: 'var(--shadow-lg)',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h4 style={{ fontWeight: 600, fontSize: '1.05rem', color: selectedImage.isError ? '#dc2626' : 'var(--text-main)', margin: 0 }}>
                  {selectedImage.isError ? `Hoja Original con Error: ${selectedImage.name}` : `Hoja Procesada con Detecciones OMR: ${selectedImage.student}`}
                </h4>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {selectedImage.isError ? 'Visualizando imagen original para verificar causa del fallo' : `Visualizando imagen procesada con calibración y recuadros detectados (${selectedImage.name})`}
                </div>
              </div>
              <button
                onClick={() => setSelectedImage(null)}
                style={{ padding: '0.5rem', borderRadius: '50%', color: 'var(--text-muted)', background: 'transparent', border: 'none', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {selectedImage.isError && (
              <div style={{ padding: '0.75rem 1.5rem', background: '#fef2f2', borderBottom: '1px solid #fee2e2', color: '#991b1b', fontSize: '0.85rem' }}>
                <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
                  <AlertTriangle size={15} color="#dc2626" />
                  <span>Estado: ERROR ({selectedImage.errorMessage || 'No se detectaron marcadores'})</span>
                </div>
                <div>{selectedImage.possibleCause}</div>
              </div>
            )}

            <div style={{ padding: '1rem', overflowY: 'auto', textAlign: 'center', background: '#0f172a' }}>
              <img
                src={selectedImage.url}
                alt="Hoja OMR"
                style={{ maxWidth: '100%', maxHeight: '68vh', objectFit: 'contain', borderRadius: '4px' }}
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.parentNode.innerHTML += '<div style="color:white;padding:2rem;">No se pudo cargar la vista previa de la imagen.</div>';
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Modal para volver a cargar ZIP corregido */}
      {showRetryModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 60,
          padding: '1.5rem',
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: 'var(--radius-lg)',
            maxWidth: '520px',
            width: '100%',
            boxShadow: 'var(--shadow-lg)',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Upload size={20} color="var(--primary)" />
                <h4 style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-main)', margin: 0 }}>
                  Volver a cargar ZIP corregido
                </h4>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (!retryLoading) {
                    setShowRetryModal(false);
                    setRetryFile(null);
                    setRetryError('');
                  }
                }}
                disabled={retryLoading}
                style={{ padding: '0.4rem', borderRadius: '50%', color: 'var(--text-muted)', background: 'transparent', border: 'none', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleRetrySubmit} style={{ padding: '1.5rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                Sube un nuevo archivo ZIP que contenga únicamente las hojas OMR que presentaron errores o necesiten ser reevaluadas. El sistema mantendrá las hojas correctas existentes y actualizará el examen.
              </p>

              {retryError && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
                  {retryError}
                </div>
              )}

              <div
                style={{
                  border: '2px dashed var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '2rem 1rem',
                  textAlign: 'center',
                  backgroundColor: 'var(--bg-app)',
                  cursor: 'pointer',
                  marginBottom: '1.25rem',
                }}
                onClick={() => document.getElementById('retry-zip-input').click()}
              >
                <Upload size={32} color="var(--text-muted)" style={{ margin: '0 auto 0.75rem auto' }} />
                <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  {retryFile ? retryFile.name : 'Haz clic para seleccionar el archivo ZIP'}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {retryFile ? `${(retryFile.size / 1024 / 1024).toFixed(2)} MB` : 'Formato .zip con imágenes PNG, JPG, JPEG'}
                </div>
                <input
                  id="retry-zip-input"
                  type="file"
                  accept=".zip,application/zip"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setRetryFile(e.target.files[0]);
                      setRetryError('');
                    }
                  }}
                  disabled={retryLoading}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => {
                    setShowRetryModal(false);
                    setRetryFile(null);
                    setRetryError('');
                  }}
                  className="btn btn-secondary"
                  disabled={retryLoading}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={retryLoading || !retryFile}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  {retryLoading ? (
                    <>
                      <RefreshCw size={16} className="spin-icon" style={{ animation: 'spin 1s linear infinite' }} />
                      <span>Procesando ZIP...</span>
                    </>
                  ) : (
                    <>
                      <Upload size={16} />
                      <span>Reintentar y Actualizar</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
