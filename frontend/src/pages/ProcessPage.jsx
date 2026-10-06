import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileArchive,
  ArrowRight,
  RefreshCw,
  Lock,
  Unlock,
  AlertCircle,
  Sliders,
  CheckCircle2,
  Trash2,
  Clock,
} from 'lucide-react';
import { api } from '../services/api';

const MAX_QUESTIONS = 40;
const DEFAULT_OPTIONS = ['A', 'B', 'C', 'D', 'E'];

export default function ProcessPage() {
  const navigate = useNavigate();

  // 1. Nombre del Examen
  const [examName, setExamName] = useState('');
  const [examNameError, setExamNameError] = useState('');

  // 2. Archivos ZIP múltiples
  const [zipFiles, setZipFiles] = useState([]);
  const [zipError, setZipError] = useState('');
  const [zipStatuses, setZipStatuses] = useState([]);

  // 3. Cantidad de preguntas y respuestas
  const [questionCount, setQuestionCount] = useState(40);
  const [answers, setAnswers] = useState(() => {
    const initial = {};
    for (let i = 1; i <= 40; i++) initial[i] = '';
    return initial;
  });

  // 4. Modalidad de puntos (Modalidad 1: Mismo valor | Modalidad 2: Puntos específicos)
  const [scoringMode, setScoringMode] = useState('EQUAL'); // 'EQUAL' | 'SPECIFIC'
  const [equalPoints, setEqualPoints] = useState('1');
  const [specificPoints, setSpecificPoints] = useState(() => {
    const initial = {};
    for (let i = 1; i <= 40; i++) initial[i] = '1';
    return initial;
  });

  // 5. Estado de validación, bloqueo de configuración y procesamiento
  const [validationError, setValidationError] = useState('');
  const [isConfigLocked, setIsConfigLocked] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processError, setProcessError] = useState('');

  // Manejador de cambio de cantidad de preguntas (Límite estricto 1 a 40)
  const handleQuestionCountChange = (count) => {
    if (isConfigLocked || isProcessing) return;
    const num = Math.max(1, Math.min(MAX_QUESTIONS, parseInt(count, 10) || 1));
    setQuestionCount(num);
    setAnswers((prev) => {
      const updated = { ...prev };
      for (let i = 1; i <= num; i++) {
        if (!updated[i]) updated[i] = '';
      }
      return updated;
    });
    setSpecificPoints((prev) => {
      const updated = { ...prev };
      for (let i = 1; i <= num; i++) {
        if (!updated[i]) updated[i] = '1';
      }
      return updated;
    });
  };

  // Asignar respuesta individual directa
  const handleAnswerChange = (qNum, val) => {
    if (isConfigLocked || isProcessing) return;
    setAnswers((prev) => ({ ...prev, [qNum]: val }));
    setValidationError('');
  };

  // Asignar puntos específicos por pregunta
  const handleSpecificPointChange = (qNum, val) => {
    if (isConfigLocked || isProcessing) return;
    setSpecificPoints((prev) => ({ ...prev, [qNum]: val }));
    setValidationError('');
  };

  // Control de incremento entero por flechas (Up/Down) preservando decimales escritos manualmente
  const handlePointKeyDown = (e, currentVal, onChange) => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      if (isConfigLocked || isProcessing) return;
      const dir = e.key === 'ArrowUp' ? 1 : -1;
      const num = parseFloat(currentVal);
      if (isNaN(num)) {
        onChange('1');
        return;
      }
      const nextVal = dir > 0 ? num + 1 : num - 1;
      if (nextVal <= 0) return;

      const strVal = String(currentVal).trim();
      const dotIdx = strVal.indexOf('.');
      const decimals = dotIdx !== -1 ? strVal.length - dotIdx - 1 : 0;
      const formatted = decimals > 0 ? nextVal.toFixed(decimals) : String(nextVal);
      onChange(formatted);
      setValidationError('');
    }
  };

  // Limpiar todas las respuestas
  const handleClearAnswers = () => {
    if (isConfigLocked || isProcessing) return;
    const updated = {};
    for (let i = 1; i <= questionCount; i++) updated[i] = '';
    setAnswers(updated);
    setValidationError('');
  };

  // Formateador legible de bytes
  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  // Manejo de archivos ZIP múltiples (NO se bloquea por el candado de configuración)
  const handleFileChange = (e) => {
    if (isProcessing) return;
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    // Validación estricta: sólo archivos con extensión .zip
    const invalidFiles = files.filter(
      (f) => !f.name.toLowerCase().endsWith('.zip')
    );

    if (invalidFiles.length > 0) {
      const invalidNames = invalidFiles.map((f) => f.name).join(', ');
      setZipError(
        invalidFiles.length === 1
          ? `${invalidNames} no es un archivo ZIP válido. Solo se permiten archivos ZIP (.zip).`
          : `Los archivos [${invalidNames}] no son archivos ZIP válidos. Solo se permiten archivos ZIP (.zip).`
      );
      e.target.value = '';
      return;
    }

    setZipError('');
    setZipFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const news = files.filter((f) => !existingNames.has(f.name));
      return [...prev, ...news];
    });
    e.target.value = '';
  };

  // Eliminar un archivo ZIP específico de la lista antes de procesar
  const handleRemoveFile = (indexToRemove) => {
    if (isProcessing) return;
    setZipFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    setZipError('');
  };

  // Validar y ejecutar el procesamiento OMR
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (isProcessing) return;

    // Validación 1: Nombre del examen
    const cleanExamName = examName.trim();
    if (!cleanExamName) {
      setExamNameError('El nombre del examen es obligatorio.');
      return;
    }
    setExamNameError('');

    // Validación 2: Archivos ZIP seleccionados
    if (!zipFiles || zipFiles.length === 0) {
      setZipError('Debes seleccionar al menos un archivo ZIP con las hojas de examen OMR.');
      return;
    }
    setZipError('');

    // Validación 3: Todas las preguntas deben tener respuesta asignada
    const missing = [];
    for (let i = 1; i <= questionCount; i++) {
      if (!answers[i]) missing.push(i);
    }

    if (missing.length > 0) {
      setValidationError(
        `Faltan respuestas por asignar en ${missing.length} pregunta(s): ${missing.slice(0, 5).map((n) => `P${n}`).join(', ')}${missing.length > 5 ? '...' : ''}`
      );
      return;
    }

    // Validación 4: Validación de puntos numéricos válidos (> 0, enteros o decimales)
    if (scoringMode === 'EQUAL') {
      const eq = parseFloat(equalPoints);
      if (isNaN(eq) || eq <= 0) {
        setValidationError('La puntuación por pregunta debe ser un número positivo mayor a 0 (ej. 1, 0.25, 1.75).');
        return;
      }
    } else {
      for (let i = 1; i <= questionCount; i++) {
        const raw = specificPoints[i];
        if (raw === undefined || raw === null || String(raw).trim() === '') {
          setValidationError(`Falta asignar puntuación a la pregunta P${i}.`);
          return;
        }
        const pt = parseFloat(raw);
        if (isNaN(pt) || pt <= 0) {
          setValidationError(`La puntuación de la pregunta P${i} debe ser un número positivo mayor a 0 (ej. 0.25, 1.5, 2.75).`);
          return;
        }
      }
    }

    setValidationError('');
    setProcessError('');

    // Inicializar estado de progreso para cada archivo ZIP
    const initialStatuses = zipFiles.map((f, i) => ({
      name: f.name,
      size: f.size,
      status: i === 0 ? 'processing' : 'pending',
      error: null,
    }));
    setZipStatuses(initialStatuses);
    setIsProcessing(true);

    try {
      // 1. Construir objeto de evaluación equivalente a evaluation.json
      const questionsInOrder = [];
      const answersInOrder = [];

      for (let i = 1; i <= questionCount; i++) {
        questionsInOrder.push(`q${i}`);
        answersInOrder.push(answers[i]);
      }

      let markingSchemes = {};
      if (scoringMode === 'EQUAL') {
        const pts = parseFloat(equalPoints) || 1;
        markingSchemes = {
          DEFAULT: {
            correct: pts,
            incorrect: 0,
            unmarked: 0,
          },
        };
      } else {
        markingSchemes = {
          DEFAULT: {
            correct: 1,
            incorrect: 0,
            unmarked: 0,
          },
        };
        for (let i = 1; i <= questionCount; i++) {
          const qKey = `q${i}`;
          const pts = parseFloat(specificPoints[i]) || 1;
          markingSchemes[`SECTION_${qKey}`] = {
            questions: [qKey],
            marking: {
              correct: pts,
              incorrect: 0,
              unmarked: 0,
            },
          };
        }
      }

      const evaluationObject = {
        source_type: 'custom',
        options: {
          questions_in_order: questionsInOrder,
          answers_in_order: answersInOrder,
          should_explain_scoring: true,
        },
        marking_schemes: markingSchemes,
      };

      // 2. Generar Blob de evaluation.json
      const evalBlob = new Blob([JSON.stringify(evaluationObject, null, 2)], {
        type: 'application/json',
      });

      // 3. Procesamiento secuencial controlado de los archivos ZIP
      let currentJobId = null;
      let hasAnySuccess = false;

      for (let i = 0; i < zipFiles.length; i++) {
        const file = zipFiles[i];
        setZipStatuses((prev) =>
          prev.map((s, idx) => (idx === i ? { ...s, status: 'processing' } : s))
        );

        const formData = new FormData();
        formData.append('zip_files', file);

        if (!currentJobId) {
          formData.append('exam_name', cleanExamName);
          formData.append('evaluation', evalBlob, 'evaluation.json');
        } else {
          formData.append('job_id', currentJobId);
        }

        try {
          const res = await api.processOMR(formData);
          if (res && res.job_id) {
            currentJobId = res.job_id;
            hasAnySuccess = true;
          }
          setZipStatuses((prev) =>
            prev.map((s, idx) => (idx === i ? { ...s, status: 'completed' } : s))
          );
        } catch (err) {
          setZipStatuses((prev) =>
            prev.map((s, idx) =>
              idx === i ? { ...s, status: 'error', error: err.message } : s
            )
          );
          if (zipFiles.length === 1) {
            throw err;
          }
        }
      }

      if (currentJobId && hasAnySuccess) {
        // Pausa breve para permitir ver el estado final de los archivos
        setTimeout(() => {
          navigate(`/results/${currentJobId}`);
        }, 1200);
      } else {
        throw new Error('No fue posible procesar ningún archivo ZIP válido.');
      }
    } catch (err) {
      setProcessError(err.message || 'Error al procesar el examen.');
      setIsProcessing(false);
    }
  };

  const filledCount = Object.keys(answers).filter(
    (k) => parseInt(k, 10) <= questionCount && answers[k] !== ''
  ).length;

  return (
    <div className="page-container" style={{ position: 'relative' }}>
      {/* 4. MENSAJE Y ANIMACIÓN DURANTE EL PROCESAMIENTO */}
      {isProcessing && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(4px)',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          padding: '2rem',
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: 'var(--radius-lg)',
            padding: '2.5rem 3rem',
            maxWidth: '480px',
            width: '100%',
            textAlign: 'center',
            boxShadow: 'var(--shadow-lg)',
            color: 'var(--text-main)',
          }}>
            <RefreshCw
              size={48}
              color="var(--primary)"
              style={{ animation: 'spin 1.2s linear infinite', margin: '0 auto 1.25rem auto' }}
            />
            <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-main)' }}>
              Estamos procesando tus exámenes...
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem', marginBottom: '1.25rem' }}>
              Extrayendo hojas OMR, detectando marcas y calculando puntuaciones de forma automatizada.
            </p>

            {/* Lista individual de progreso por archivo ZIP */}
            {zipStatuses.length > 0 && (
              <div style={{
                maxHeight: '190px',
                overflowY: 'auto',
                textAlign: 'left',
                margin: '1rem 0 1.25rem 0',
                border: '1px solid #e2e8f0',
                borderRadius: 'var(--radius-sm)',
                padding: '0.6rem 0.85rem',
                backgroundColor: '#f8fafc',
              }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.45rem' }}>
                  Progreso por archivo ({zipStatuses.filter(s => s.status === 'completed' || s.status === 'error').length} de {zipStatuses.length}):
                </div>
                {zipStatuses.map((item, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.35rem 0',
                    borderBottom: idx < zipStatuses.length - 1 ? '1px solid #e2e8f0' : 'none',
                    fontSize: '0.825rem',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }} title={item.name}>
                      {item.status === 'pending' && <Clock size={15} color="#94a3b8" />}
                      {item.status === 'processing' && <RefreshCw size={15} color="var(--primary)" style={{ animation: 'spin 1s linear infinite' }} />}
                      {item.status === 'completed' && <CheckCircle2 size={15} color="#10b981" />}
                      {item.status === 'error' && <AlertCircle size={15} color="var(--danger)" />}
                      <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>{item.name}</span>
                    </div>
                    <span style={{
                      fontWeight: 600,
                      fontSize: '0.725rem',
                      padding: '0.15rem 0.45rem',
                      borderRadius: '9999px',
                      backgroundColor:
                        item.status === 'completed' ? '#dcfce7' :
                        item.status === 'processing' ? '#e0e7ff' :
                        item.status === 'error' ? '#fee2e2' : '#f1f5f9',
                      color:
                        item.status === 'completed' ? '#166534' :
                        item.status === 'processing' ? '#3730a3' :
                        item.status === 'error' ? '#991b1b' : '#64748b',
                    }}>
                      {item.status === 'pending' && 'Pendiente'}
                      {item.status === 'processing' && 'Procesando'}
                      {item.status === 'completed' && 'Completado'}
                      {item.status === 'error' && 'Error'}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Animación de puntos ● ● ● */}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}>
              <span className="pulsing-dot dot-1" style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--primary)' }}></span>
              <span className="pulsing-dot dot-2" style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--primary)' }}></span>
              <span className="pulsing-dot dot-3" style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--primary)' }}></span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '1.25rem' }}>
              Por favor no recargues la página
            </div>
          </div>
        </div>
      )}

      {/* Encabezado de la página */}
      <div style={{ marginBottom: '1.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
            Nuevo Procesamiento OMR
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Asigna el nombre, carga el archivo ZIP y configura la clave de respuestas y puntuación.
          </p>
        </div>

        {/* Candado interactivo en el encabezado principal */}
        <button
          type="button"
          onClick={() => setIsConfigLocked(!isConfigLocked)}
          disabled={isProcessing}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            backgroundColor: isConfigLocked ? '#fef3c7' : '#ffffff',
            color: isConfigLocked ? '#b45309' : '#475569',
            padding: '0.45rem 0.95rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            fontSize: '0.875rem',
            border: isConfigLocked ? '1px solid #f59e0b' : '1px solid var(--border)',
            cursor: isProcessing ? 'not-allowed' : 'pointer',
            boxShadow: 'var(--shadow-sm)',
            transition: 'all 0.15s ease',
          }}
          title={isConfigLocked ? 'Configuración bloqueada. Haz clic para desbloquear y permitir cambios.' : 'Configuración editable. Haz clic para bloquear y proteger de cambios accidentales.'}
        >
          {isConfigLocked ? <Lock size={16} color="#b45309" /> : <Unlock size={16} color="#64748b" />}
          <span>{isConfigLocked ? '🔒 Configuración Bloqueada' : '🔓 Configuración Desbloqueada'}</span>
        </button>
      </div>

      {processError && (
        <div style={{
          backgroundColor: 'var(--danger-light)',
          color: 'var(--danger)',
          padding: '1rem',
          borderRadius: 'var(--radius-md)',
          marginBottom: '1.5rem',
          border: '1px solid #fecaca',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <AlertCircle size={20} />
          <span>{processError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* PASO 1: Nombre del examen y Subida de ZIP (No se bloquean con el candado) */}
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: 'var(--primary)',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.85rem'
            }}>1</div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>Información del Examen y Archivo ZIP</h3>
          </div>

          {/* NOMBRE DEL EXAMEN */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.4rem', color: 'var(--text-main)' }}>
              Nombre del examen <span style={{ color: 'var(--danger)' }}>*</span>
            </label>
            <input
              type="text"
              placeholder="Ejemplo: Prueba de selección Ingeniería 2026"
              value={examName}
              onChange={(e) => {
                if (isProcessing) return;
                setExamName(e.target.value);
                setExamNameError('');
              }}
              disabled={isProcessing}
              className="form-input"
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                fontSize: '0.95rem',
                borderColor: examNameError ? 'var(--danger)' : undefined,
              }}
            />
            {examNameError && (
              <div style={{ color: 'var(--danger)', fontSize: '0.825rem', marginTop: '0.35rem' }}>
                {examNameError}
              </div>
            )}
          </div>

          {/* Carga de archivos ZIP múltiples */}
          <label className="dropzone-container" style={{ display: 'block', cursor: isProcessing ? 'not-allowed' : 'pointer' }}>
            <input
              type="file"
              multiple
              accept=".zip"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              disabled={isProcessing}
            />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
              <FileArchive size={40} color={zipFiles.length > 0 ? '#10b981' : 'var(--primary)'} />
              <div>
                <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-main)' }}>
                  {zipFiles.length > 0
                    ? 'Haz clic para seleccionar o arrastra más archivos .zip'
                    : 'Haz clic para seleccionar o arrastra aquí tus archivos .zip'}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.825rem' }}>
                  Puedes seleccionar múltiples archivos .zip simultáneamente (.zip)
                </div>
              </div>
            </div>
          </label>

          {/* LISTA DE ARCHIVOS ZIP SELECCIONADOS */}
          {zipFiles.length > 0 && (
            <div style={{
              marginTop: '1.25rem',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              backgroundColor: '#f8fafc',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)' }}>
                  Archivos seleccionados ({zipFiles.length}):
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Tamaño total: {formatFileSize(zipFiles.reduce((acc, f) => acc + f.size, 0))}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '240px', overflowY: 'auto' }}>
                {zipFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.55rem 0.85rem',
                      fontSize: '0.875rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                      <CheckCircle2 size={16} color="#10b981" style={{ flexShrink: 0 }} />
                      <span style={{ fontWeight: 600, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={file.name}>
                        {file.name}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', flexShrink: 0 }}>
                        {formatFileSize(file.size)}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      disabled={isProcessing}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--danger)',
                        cursor: isProcessing ? 'not-allowed' : 'pointer',
                        padding: '0.25rem',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '4px',
                      }}
                      title={`Eliminar ${file.name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {zipError && (
            <div style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.65rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{zipError}</span>
            </div>
          )}
        </div>

        {/* PASO 2: Configuración de Puntuación */}
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'var(--primary)',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.85rem'
              }}>2</div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>Configuración de Puntos</h3>
            </div>

            {/* Candado pequeño de bloqueo/desbloqueo */}
            <button
              type="button"
              onClick={() => setIsConfigLocked(!isConfigLocked)}
              disabled={isProcessing}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--radius-sm)',
                border: isConfigLocked ? '1px solid #f59e0b' : '1px solid var(--border)',
                backgroundColor: isConfigLocked ? '#fef3c7' : '#ffffff',
                color: isConfigLocked ? '#b45309' : '#475569',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
              title={isConfigLocked ? 'Configuración bloqueada. Haz clic para desbloquear.' : 'Configuración editable. Haz clic para bloquear.'}
            >
              {isConfigLocked ? <Lock size={14} color="#b45309" /> : <Unlock size={14} color="#64748b" />}
              <span>{isConfigLocked ? '🔒 Bloqueado' : '🔓 Desbloqueado'}</span>
            </button>
          </div>

          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            {/* Modalidad 1: Mismo valor */}
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: (isConfigLocked || isProcessing) ? 'not-allowed' : 'pointer',
              fontWeight: 500,
              fontSize: '0.925rem',
              opacity: (isConfigLocked || isProcessing) ? 0.75 : 1,
            }}>
              <input
                type="radio"
                name="scoringMode"
                value="EQUAL"
                checked={scoringMode === 'EQUAL'}
                onChange={() => {
                  if (isConfigLocked || isProcessing) return;
                  setScoringMode('EQUAL');
                  setValidationError('');
                }}
                disabled={isConfigLocked || isProcessing}
              />
              <span><strong>Modalidad 1:</strong> Mismo valor para todas las preguntas</span>
            </label>

            {/* Modalidad 2: Puntos específicos */}
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: (isConfigLocked || isProcessing) ? 'not-allowed' : 'pointer',
              fontWeight: 500,
              fontSize: '0.925rem',
              opacity: (isConfigLocked || isProcessing) ? 0.75 : 1,
            }}>
              <input
                type="radio"
                name="scoringMode"
                value="SPECIFIC"
                checked={scoringMode === 'SPECIFIC'}
                onChange={() => {
                  if (isConfigLocked || isProcessing) return;
                  setScoringMode('SPECIFIC');
                  setValidationError('');
                }}
                disabled={isConfigLocked || isProcessing}
              />
              <span><strong>Modalidad 2:</strong> Puntos específicos por pregunta</span>
            </label>
          </div>

          {scoringMode === 'EQUAL' && (
            <div style={{
              backgroundColor: 'var(--bg-app)',
              padding: '0.85rem 1.25rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.75rem',
            }}>
              <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
                Puntos por pregunta:
              </label>
              <input
                type="number"
                step="any"
                min="0"
                placeholder="1.0"
                value={equalPoints}
                onChange={(e) => {
                  if (isConfigLocked || isProcessing) return;
                  setEqualPoints(e.target.value);
                  setValidationError('');
                }}
                onKeyDown={(e) => handlePointKeyDown(e, equalPoints, setEqualPoints)}
                disabled={isConfigLocked || isProcessing}
                style={{
                  width: '90px',
                  padding: '0.35rem 0.5rem',
                  fontSize: '0.9rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  backgroundColor: isConfigLocked ? '#f1f5f9' : '#ffffff',
                }}
              />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                (Puntuación máxima total: {((parseFloat(equalPoints) || 0) * questionCount).toFixed(2)} pts)
              </span>
            </div>
          )}
        </div>

        {/* PASO 3: Clave de Respuestas */}
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'var(--primary)',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.85rem'
              }}>3</div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>Clave de Respuestas</h3>
                  {/* Candado pequeño interactivo al lado del título */}
                  <button
                    type="button"
                    onClick={() => setIsConfigLocked(!isConfigLocked)}
                    disabled={isProcessing}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      padding: '0.2rem 0.5rem',
                      borderRadius: 'var(--radius-sm)',
                      border: isConfigLocked ? '1px solid #f59e0b' : '1px solid var(--border)',
                      backgroundColor: isConfigLocked ? '#fef3c7' : '#ffffff',
                      color: isConfigLocked ? '#b45309' : '#475569',
                      cursor: isProcessing ? 'not-allowed' : 'pointer',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                    }}
                    title={isConfigLocked ? 'Configuración bloqueada. Haz clic para desbloquear.' : 'Configuración editable. Haz clic para bloquear.'}
                  >
                    {isConfigLocked ? <Lock size={13} color="#b45309" /> : <Unlock size={13} color="#64748b" />}
                    <span>{isConfigLocked ? '🔒 Bloqueado' : '🔓 Desbloqueado'}</span>
                  </button>
                </div>
                <div style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
                  {filledCount} de {questionCount} preguntas con respuesta asignada
                </div>
              </div>
            </div>

            {/* Selector de cantidad de preguntas y botón Limpiar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                  Preguntas (máx 40):
                </label>
                <select
                  value={questionCount}
                  onChange={(e) => handleQuestionCountChange(e.target.value)}
                  className="form-select"
                  style={{ width: '85px', padding: '0.35rem 0.65rem', fontSize: '0.875rem' }}
                  disabled={isConfigLocked || isProcessing}
                >
                  {[5, 10, 15, 20, 25, 30, 35, 40].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={handleClearAnswers}
                className="btn btn-secondary"
                style={{ padding: '0.35rem 0.65rem', fontSize: '0.775rem', color: 'var(--danger)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                disabled={isConfigLocked || isProcessing}
              >
                <Trash2 size={14} />
                <span>Limpiar</span>
              </button>
            </div>
          </div>

          {validationError && (
            <div style={{
              backgroundColor: 'var(--warning-light)',
              color: 'var(--warning)',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1rem',
              fontSize: '0.875rem',
              border: '1px solid #fde68a',
            }}>
              {validationError}
            </div>
          )}

          {/* Grilla dinámica de preguntas con opciones A-E y puntos específicos */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
            gap: '0.75rem',
            maxHeight: '400px',
            overflowY: 'auto',
            padding: '0.65rem',
            background: 'var(--bg-app)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
          }}>
            {Array.from({ length: questionCount }, (_, idx) => {
              const qNum = idx + 1;
              const selectedAns = answers[qNum] || '';
              return (
                <div
                  key={qNum}
                  style={{
                    background: '#ffffff',
                    padding: '0.65rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    border: selectedAns ? '1px solid var(--primary)' : '1px solid var(--border)',
                    boxShadow: 'var(--shadow-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.35rem',
                    opacity: isConfigLocked ? 0.8 : 1,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-main)' }}>
                      P{qNum}
                    </span>

                    {/* Si es modalidad específica, input editable de puntos con soporte decimal libre */}
                    {scoringMode === 'SPECIFIC' ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Pts:</span>
                        <input
                          type="number"
                          step="any"
                          min="0"
                          placeholder="1"
                          value={specificPoints[qNum] ?? '1'}
                          onChange={(e) => handleSpecificPointChange(qNum, e.target.value)}
                          onKeyDown={(e) => handlePointKeyDown(e, specificPoints[qNum] ?? '1', (val) => handleSpecificPointChange(qNum, val))}
                          disabled={isConfigLocked || isProcessing}
                          style={{
                            width: '58px',
                            padding: '0.15rem 0.3rem',
                            fontSize: '0.75rem',
                            textAlign: 'center',
                            borderRadius: '3px',
                            border: '1px solid var(--border)',
                            backgroundColor: isConfigLocked ? '#f1f5f9' : '#ffffff',
                            color: isConfigLocked ? 'var(--text-muted)' : 'var(--text-main)',
                            fontWeight: 600,
                          }}
                        />
                      </div>
                    ) : selectedAns ? (
                      <span style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: 'white',
                        backgroundColor: 'var(--primary)',
                        width: '18px',
                        height: '18px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        {selectedAns}
                      </span>
                    ) : null}
                  </div>

                  {/* Opciones directas A B C D E */}
                  <div style={{ display: 'flex', gap: '0.2rem' }}>
                    {DEFAULT_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => handleAnswerChange(qNum, opt)}
                        style={{
                          flex: 1,
                          padding: '0.25rem 0',
                          fontSize: '0.8rem',
                          fontWeight: selectedAns === opt ? 700 : 500,
                          borderRadius: '4px',
                          border: selectedAns === opt ? '1px solid var(--primary)' : '1px solid var(--border)',
                          backgroundColor: selectedAns === opt ? 'var(--primary)' : '#ffffff',
                          color: selectedAns === opt ? 'white' : 'var(--text-main)',
                          transition: 'all 0.1s ease',
                          cursor: (isConfigLocked || isProcessing) ? 'not-allowed' : 'pointer',
                        }}
                        disabled={isConfigLocked || isProcessing}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Resumen visual de la clave */}
          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Resumen visual de respuestas y puntos:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
              {Array.from({ length: questionCount }, (_, idx) => {
                const qNum = idx + 1;
                const ans = answers[qNum];
                const pt = scoringMode === 'SPECIFIC' ? (specificPoints[qNum] ?? '1') : equalPoints;
                return (
                  <span
                    key={qNum}
                    style={{
                      fontSize: '0.75rem',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      background: ans ? 'var(--primary-light)' : '#f1f5f9',
                      color: ans ? 'var(--primary)' : '#94a3b8',
                      fontWeight: ans ? 600 : 400,
                      border: ans ? '1px solid #bfdbfe' : '1px solid #e2e8f0',
                    }}
                  >
                    P{qNum}: <strong>{ans || '-'}</strong> ({pt} pt)
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* Botón de acción principal */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button
            type="submit"
            className="btn btn-primary"
            style={{
              padding: '0.85rem 2rem',
              fontSize: '1.05rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              opacity: isProcessing ? 0.75 : 1,
              cursor: isProcessing ? 'not-allowed' : 'pointer',
            }}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <RefreshCw size={20} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Procesando exámenes...</span>
              </>
            ) : (
              <>
                <span>Procesar exámenes</span>
                <ArrowRight size={20} />
              </>
            )}
          </button>
        </div>
      </form>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulseDot {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1.1); opacity: 1; }
        }
        .pulsing-dot.dot-1 { animation: pulseDot 1.4s infinite ease-in-out; }
        .pulsing-dot.dot-2 { animation: pulseDot 1.4s infinite ease-in-out 0.2s; }
        .pulsing-dot.dot-3 { animation: pulseDot 1.4s infinite ease-in-out 0.4s; }
      `}</style>
    </div>
  );
}
