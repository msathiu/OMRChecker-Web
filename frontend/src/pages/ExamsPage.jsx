import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Plus,
  Edit2,
  Trash2,
  PlayCircle,
  CheckCircle2,
  AlertCircle,
  Users,
  Lock,
  Layers,
  Search,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

const MAX_QUESTIONS = 40;
const OPTIONS = ['A', 'B', 'C', 'D', 'E'];

export default function ExamsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [exams, setExams] = useState([]);
  const [usersList, setUsersList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal de creación / edición
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingExamId, setEditingExamId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    question_count: 40,
    scoring_mode: 'EQUAL',
    equal_points: '1.0',
    specific_points: {},
    answers: {},
    enabled_for_all: true,
    enabled_user_ids: [],
  });
  const [formError, setFormError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Modal de asignación a usuarios (sin ZIP)
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [assigningExam, setAssigningExam] = useState(null);
  const [assignedUsers, setAssignedUsers] = useState([]);
  const [selectedAssignUserIds, setSelectedAssignUserIds] = useState([]);
  const [loadingAssignments, setLoadingAssignments] = useState(false);
  const [assigningError, setAssigningError] = useState('');
  const [isSavingAssignments, setIsSavingAssignments] = useState(false);

  const isEditorOrAdmin = user && (user.role === 'editor' || user.role === 'admin');

  const fetchExams = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getExams();
      setExams(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Error al cargar los exámenes.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    if (!isEditorOrAdmin) return;
    try {
      const data = await api.getUsers();
      setUsersList(Array.isArray(data) ? data : []);
    } catch {
      // Ignorar si no es admin y users falla
    }
  };

  useEffect(() => {
    fetchExams();
    fetchUsers();
  }, [user]);

  const handleOpenCreateModal = () => {
    setEditingExamId(null);
    const initialAnswers = {};
    const initialSpecPoints = {};
    for (let i = 1; i <= 40; i++) {
      initialAnswers[i] = 'A';
      initialSpecPoints[i] = '1.0';
    }
    setFormData({
      name: '',
      description: '',
      question_count: 40,
      scoring_mode: 'EQUAL',
      equal_points: '1.0',
      specific_points: initialSpecPoints,
      answers: initialAnswers,
      enabled_for_all: true,
      enabled_user_ids: [],
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (exam) => {
    setEditingExamId(exam.id);
    const answersObj = exam.answers || {};
    const specObj = exam.specific_points || {};
    const filledAnswers = {};
    const filledSpec = {};
    for (let i = 1; i <= exam.question_count; i++) {
      filledAnswers[i] = answersObj[String(i)] || 'A';
      filledSpec[i] = String(specObj[String(i)] !== undefined ? specObj[String(i)] : '1.0');
    }

    setFormData({
      name: exam.name || '',
      description: exam.description || '',
      question_count: exam.question_count || 40,
      scoring_mode: exam.scoring_mode || 'EQUAL',
      equal_points: String(exam.equal_points || '1.0'),
      specific_points: filledSpec,
      answers: filledAnswers,
      enabled_for_all: exam.enabled_for_all !== false,
      enabled_user_ids: exam.enabled_user_ids || [],
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleDeleteExam = async (examId, examName) => {
    if (!window.confirm(`¿Estás seguro de que deseas eliminar el examen "${examName}"?`)) {
      return;
    }
    try {
      await api.deleteExam(examId);
      setSuccessMsg(`Examen "${examName}" eliminado correctamente.`);
      fetchExams();
    } catch (err) {
      setError(err.message || 'Error al eliminar el examen.');
    }
  };

  const handleOpenAssignModal = async (exam) => {
    setAssigningExam(exam);
    setIsAssignModalOpen(true);
    setLoadingAssignments(true);
    setAssigningError('');
    try {
      const assignments = await api.getExamAssignments(exam.id);
      setAssignedUsers(assignments);
      setSelectedAssignUserIds(assignments.map((a) => a.id));
    } catch (err) {
      setAssigningError(err.message || 'Error al cargar asignaciones.');
    } finally {
      setLoadingAssignments(false);
    }
  };

  const handleSaveAssignments = async () => {
    if (!assigningExam) return;
    setIsSavingAssignments(true);
    setAssigningError('');
    try {
      const res = await api.assignExam(assigningExam.id, selectedAssignUserIds);
      setSuccessMsg(res.message || 'Asignaciones actualizadas exitosamente.');
      setIsAssignModalOpen(false);
      fetchExams();
    } catch (err) {
      setAssigningError(err.message || 'Error al guardar asignaciones.');
    } finally {
      setIsSavingAssignments(false);
    }
  };

  const handleFillAllAnswers = (option) => {
    const updated = { ...formData.answers };
    for (let i = 1; i <= formData.question_count; i++) {
      updated[i] = option;
    }
    setFormData((prev) => ({ ...prev, answers: updated }));
  };

  const handleSaveExam = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!formData.name.trim()) {
      setFormError('El nombre del examen es obligatorio.');
      return;
    }

    const qCount = parseInt(formData.question_count, 10);
    if (isNaN(qCount) || qCount < 1 || qCount > 40) {
      setFormError('La cantidad de preguntas debe estar entre 1 y 40.');
      return;
    }

    // Validar respuestas
    const cleanAnswers = {};
    for (let i = 1; i <= qCount; i++) {
      const ans = formData.answers[i];
      if (!ans || !OPTIONS.includes(ans)) {
        setFormError(`Debe asignar una respuesta válida (A, B, C, D o E) para la pregunta ${i}.`);
        return;
      }
      cleanAnswers[String(i)] = ans;
    }

    // Validar puntos
    const cleanSpecPoints = {};
    if (formData.scoring_mode === 'SPECIFIC') {
      for (let i = 1; i <= qCount; i++) {
        const val = parseFloat(formData.specific_points[i]);
        if (isNaN(val) || val <= 0) {
          setFormError(`El puntaje para la pregunta ${i} debe ser un número positivo.`);
          return;
        }
        cleanSpecPoints[String(i)] = val;
      }
    }

    const payload = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      question_count: qCount,
      scoring_mode: formData.scoring_mode,
      equal_points: parseFloat(formData.equal_points) || 1.0,
      specific_points: formData.scoring_mode === 'SPECIFIC' ? cleanSpecPoints : null,
      answers: cleanAnswers,
      enabled_for_all: Boolean(formData.enabled_for_all),
      enabled_user_ids: formData.enabled_for_all ? [] : formData.enabled_user_ids,
    };

    setIsSaving(true);
    try {
      if (editingExamId) {
        await api.updateExam(editingExamId, payload);
        setSuccessMsg('Examen actualizado exitosamente.');
      } else {
        await api.createExam(payload);
        setSuccessMsg('Examen creado y configurado exitosamente.');
      }
      setIsModalOpen(false);
      fetchExams();
    } catch (err) {
      setFormError(err.message || 'Error al guardar el examen.');
    } finally {
      setIsSaving(false);
    }
  };

  const filteredExams = exams.filter((e) => {
    const term = searchTerm.toLowerCase();
    return (
      (e.name && e.name.toLowerCase().includes(term)) ||
      (e.creator_name && e.creator_name.toLowerCase().includes(term)) ||
      (e.description && e.description.toLowerCase().includes(term))
    );
  });

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
            {user?.role === 'usuario'
              ? 'Mis Exámenes'
              : user?.role === 'editor'
              ? 'Mis Exámenes'
              : 'Gestión Global de Exámenes'}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            {user?.role === 'usuario'
              ? 'Exámenes que tienes asignados para procesar hojas de respuestas.'
              : isEditorOrAdmin
              ? 'Configura las pautas de respuestas correctas, modalidad de puntuación y usuarios asignados.'
              : 'Administración de exámenes en el sistema.'}
          </p>
        </div>

        {isEditorOrAdmin && (
          <button
            type="button"
            onClick={handleOpenCreateModal}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <Plus size={18} />
            <span>Crear Nuevo Examen</span>
          </button>
        )}
      </div>

      {successMsg && (
        <div style={{ padding: '0.75rem 1rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', borderRadius: 'var(--radius-md)', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between' }}>
          <span>{successMsg}</span>
          <button type="button" onClick={() => setSuccessMsg('')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>×</button>
        </div>
      )}

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 'var(--radius-md)', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Buscador */}
      <div style={{ marginBottom: '1.25rem', position: 'relative', maxWidth: '400px' }}>
        <Search size={18} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        <input
          type="text"
          placeholder="Buscar examen por título o profesor..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="form-control"
          style={{ paddingLeft: '2.5rem' }}
        />
      </div>

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Cargando exámenes...
        </div>
      ) : filteredExams.length === 0 ? (
        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
          <FileText size={40} color="var(--text-muted)" style={{ margin: '0 auto 1rem auto' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
            {user?.role === 'usuario' ? 'Todavía no tienes exámenes asignados' : 'No se encontraron exámenes'}
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            {user?.role === 'usuario'
              ? 'Ponte en contacto con tu profesor o administrador para que te asigne un examen.'
              : isEditorOrAdmin
              ? 'Crea tu primer examen configurando la clave de respuestas correctas.'
              : 'No hay exámenes registrados que coincidan con la búsqueda.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {filteredExams.map((exam) => (
            <div key={exam.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                    {exam.name}
                  </h3>
                  <span
                    style={{
                      padding: '0.2rem 0.5rem',
                      borderRadius: '999px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      background: exam.is_active ? '#ecfdf5' : '#f3f4f6',
                      color: exam.is_active ? '#065f46' : '#6b7280',
                    }}
                  >
                    {exam.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </div>

                {exam.description && (
                  <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', marginBottom: '0.75rem', lineHeight: 1.4 }}>
                    {exam.description}
                  </p>
                )}

                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '1rem' }}>
                  <div><strong>Preguntas:</strong> {exam.question_count}</div>
                  <div>
                    <strong>Puntuación:</strong>{' '}
                    {exam.scoring_mode === 'EQUAL' ? `${exam.equal_points} pts c/u` : 'Puntaje específico'}
                  </div>
                  <div>
                    <strong>Profesor/Editor:</strong> {exam.creator_name} ({exam.creator_email})
                  </div>
                  {isEditorOrAdmin && (
                    <div>
                      <strong>Estudiantes Asignados:</strong> {exam.assigned_count ?? 0}
                    </div>
                  )}
                  <div>
                    <strong>Visibilidad:</strong> {exam.enabled_for_all ? 'Habilitado para todos' : 'Usuarios asignados'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => navigate(`/process?examId=${exam.id}`)}
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '0.45rem 0.75rem', fontSize: '0.825rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
                >
                  <PlayCircle size={16} />
                  <span>Subir Hojas (ZIP)</span>
                </button>

                {isEditorOrAdmin && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleOpenAssignModal(exam)}
                      className="btn btn-secondary"
                      style={{ padding: '0.45rem 0.65rem' }}
                      title="Asignar examen a usuarios sin subir ZIP"
                    >
                      <Users size={15} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenEditModal(exam)}
                      className="btn btn-secondary"
                      style={{ padding: '0.45rem 0.65rem' }}
                      title="Editar configuración y respuestas"
                    >
                      <Edit2 size={15} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteExam(exam.id, exam.name)}
                      className="btn btn-secondary"
                      style={{ padding: '0.45rem 0.65rem', color: '#dc2626' }}
                      title="Eliminar examen"
                    >
                      <Trash2 size={15} />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MODAL CREAR / EDITAR EXAMEN */}
      {isModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '850px', width: '100%', maxHeight: '90vh', overflowY: 'auto', background: '#ffffff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
                {editingExamId ? 'Modificar Configuración de Examen' : 'Nuevo Examen OMR'}
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                &times;
              </button>
            </div>

            {formError && (
              <div style={{ padding: '0.75rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 'var(--radius-md)', marginBottom: '1rem', fontSize: '0.875rem' }}>
                {formError}
              </div>
            )}

            <form onSubmit={handleSaveExam}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label className="form-label">Nombre del Examen *</label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                    placeholder="Ej. Examen Parcial de Matemáticas"
                    className="form-control"
                  />
                </div>

                <div>
                  <label className="form-label">Cantidad de Preguntas (1 a 40)</label>
                  <input
                    type="number"
                    min="1"
                    max="40"
                    value={formData.question_count}
                    onChange={(e) => {
                      const count = Math.max(1, Math.min(40, parseInt(e.target.value, 10) || 1));
                      setFormData((p) => ({ ...p, question_count: count }));
                    }}
                    className="form-control"
                  />
                </div>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Descripción (opcional)</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                  placeholder="Detalles adicionales, asignatura o grupo"
                  className="form-control"
                />
              </div>

              {/* Modalidad de Puntuación */}
              <div style={{ marginBottom: '1.25rem', padding: '1rem', background: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                <label className="form-label" style={{ marginBottom: '0.5rem', fontWeight: 600 }}>
                  Modalidad de Puntuación
                </label>
                <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.75rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="modal_scoring"
                      checked={formData.scoring_mode === 'EQUAL'}
                      onChange={() => setFormData((p) => ({ ...p, scoring_mode: 'EQUAL' }))}
                    />
                    <span>Mismo valor para todas las preguntas</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="modal_scoring"
                      checked={formData.scoring_mode === 'SPECIFIC'}
                      onChange={() => setFormData((p) => ({ ...p, scoring_mode: 'SPECIFIC' }))}
                    />
                    <span>Puntaje específico por pregunta</span>
                  </label>
                </div>

                {formData.scoring_mode === 'EQUAL' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Puntos por pregunta:</label>
                    <input
                      type="number"
                      step="any"
                      min="0.01"
                      value={formData.equal_points}
                      onChange={(e) => setFormData((p) => ({ ...p, equal_points: e.target.value }))}
                      className="form-control"
                      style={{ width: '100px' }}
                    />
                  </div>
                )}
              </div>

              {/* Relleno rápido de pauta */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <label className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                  Pauta de Respuestas Correctas
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Marcar todas como:</span>
                  {OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => handleFillAllAnswers(opt)}
                      className="btn btn-secondary"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tabla de preguntas y respuestas */}
              <div style={{ maxHeight: '250px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '0.5rem', marginBottom: '1.25rem', background: '#ffffff' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '0.5rem' }}>
                  {Array.from({ length: formData.question_count }, (_, idx) => {
                    const qNum = idx + 1;
                    return (
                      <div key={qNum} style={{ padding: '0.4rem', border: '1px solid #e2e8f0', borderRadius: '4px', background: '#f8fafc' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-main)' }}>P{qNum}</span>
                          {formData.scoring_mode === 'SPECIFIC' && (
                            <input
                              type="number"
                              step="any"
                              min="0.01"
                              placeholder="Pts"
                              value={formData.specific_points[qNum] || '1.0'}
                              onChange={(e) => {
                                const val = e.target.value;
                                setFormData((p) => ({
                                  ...p,
                                  specific_points: { ...p.specific_points, [qNum]: val },
                                }));
                              }}
                              style={{ width: '45px', fontSize: '0.75rem', padding: '0.1rem 0.2rem', textAlign: 'center' }}
                            />
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: '2px' }}>
                          {OPTIONS.map((opt) => {
                            const isSelected = formData.answers[qNum] === opt;
                            return (
                              <button
                                key={opt}
                                type="button"
                                onClick={() => {
                                  setFormData((p) => ({
                                    ...p,
                                    answers: { ...p.answers, [qNum]: opt },
                                  }));
                                }}
                                style={{
                                  flex: 1,
                                  padding: '0.25rem 0',
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  borderRadius: '2px',
                                  border: isSelected ? '1px solid #2563eb' : '1px solid #cbd5e1',
                                  backgroundColor: isSelected ? '#2563eb' : '#ffffff',
                                  color: isSelected ? '#ffffff' : '#334155',
                                  cursor: 'pointer',
                                }}
                              >
                                {opt}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Asignación de Usuarios Habilitados */}
              <div style={{ marginBottom: '1.25rem', padding: '0.75rem', background: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={formData.enabled_for_all}
                    onChange={(e) => setFormData((p) => ({ ...p, enabled_for_all: e.target.checked }))}
                  />
                  <span>Habilitado para todos los usuarios con rol 'usuario'</span>
                </label>

                {!formData.enabled_for_all && usersList.length > 0 && (
                  <div style={{ marginTop: '0.75rem', maxHeight: '120px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '4px', padding: '0.5rem', background: '#ffffff' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                      Selecciona qué usuarios pueden ver y procesar este examen:
                    </div>
                    {usersList
                      .filter((u) => u.role === 'usuario')
                      .map((u) => {
                        const checked = formData.enabled_user_ids.includes(u.id);
                        return (
                          <label key={u.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.825rem', padding: '0.2rem 0', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => {
                                const newIds = e.target.checked
                                  ? [...formData.enabled_user_ids, u.id]
                                  : formData.enabled_user_ids.filter((id) => id !== u.id);
                                setFormData((p) => ({ ...p, enabled_user_ids: newIds }));
                              }}
                            />
                            <span>{u.nombre} ({u.correo})</span>
                          </label>
                        );
                      })}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={isSaving}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSaving}
                >
                  {isSaving ? 'Guardando...' : editingExamId ? 'Guardar Cambios' : 'Crear Examen'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL DE ASIGNACIÓN A USUARIOS (SIN REQUERIR ZIP) */}
      {isAssignModalOpen && assigningExam && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '600px', width: '100%', maxHeight: '90vh', overflowY: 'auto', background: '#ffffff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                  Asignar Examen a Usuarios
                </h3>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  {assigningExam.name} ({assigningExam.question_count} preguntas)
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsAssignModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                &times;
              </button>
            </div>

            {assigningError && (
              <div style={{ padding: '0.75rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 'var(--radius-md)', marginBottom: '1rem', fontSize: '0.875rem' }}>
                {assigningError}
              </div>
            )}

            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Selecciona los estudiantes con rol <strong>usuario</strong> que tendrán acceso para visualizar y subir hojas de respuestas a este examen. La asignación es inmediata y no requiere subir ningún archivo ZIP.
            </p>

            {loadingAssignments ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                Cargando asignaciones actuales...
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    Estudiantes disponibles ({usersList.filter((u) => u.role === 'usuario').length}):
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      onClick={() => {
                        const allIds = usersList.filter((u) => u.role === 'usuario').map((u) => u.id);
                        setSelectedAssignUserIds(allIds);
                      }}
                      className="btn btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    >
                      Seleccionar Todos
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedAssignUserIds([])}
                      className="btn btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    >
                      Deseleccionar Todos
                    </button>
                  </div>
                </div>

                <div style={{ maxHeight: '250px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '0.5rem', background: '#f8fafc', marginBottom: '1.25rem' }}>
                  {usersList.filter((u) => u.role === 'usuario').length === 0 ? (
                    <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No hay usuarios con rol 'usuario' registrados en el sistema.
                    </div>
                  ) : (
                    usersList
                      .filter((u) => u.role === 'usuario')
                      .map((u) => {
                        const isChecked = selectedAssignUserIds.includes(u.id);
                        return (
                          <label
                            key={u.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '0.5rem 0.75rem',
                              borderRadius: '4px',
                              background: isChecked ? '#eff6ff' : '#ffffff',
                              border: isChecked ? '1px solid #bfdbfe' : '1px solid #e2e8f0',
                              marginBottom: '0.35rem',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedAssignUserIds((prev) => [...prev, u.id]);
                                  } else {
                                    setSelectedAssignUserIds((prev) => prev.filter((id) => id !== u.id));
                                  }
                                }}
                              />
                              <div>
                                <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
                                  {u.nombre}
                                </div>
                                <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
                                  {u.correo}
                                </div>
                              </div>
                            </div>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isChecked ? '#2563eb' : '#94a3b8' }}>
                              {isChecked ? 'Asignado' : 'No asignado'}
                            </span>
                          </label>
                        );
                      })
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {selectedAssignUserIds.length} estudiante(s) seleccionados
                  </span>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button
                      type="button"
                      onClick={() => setIsAssignModalOpen(false)}
                      className="btn btn-secondary"
                      disabled={isSavingAssignments}
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveAssignments}
                      className="btn btn-primary"
                      disabled={isSavingAssignments}
                    >
                      {isSavingAssignments ? 'Guardando...' : 'Guardar Asignaciones'}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

