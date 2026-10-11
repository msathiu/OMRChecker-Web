import React, { useEffect, useState } from 'react';
import {
  Users,
  UserPlus,
  Edit2,
  Trash2,
  Activity,
  Shield,
  CheckCircle2,
  XCircle,
  Search,
  Clock,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function UsersManagementPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal Crear Usuario
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newUserData, setNewUserData] = useState({
    nombre: '',
    correo: '',
    clave: '',
    role: 'usuario',
  });
  const [createError, setCreateError] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Modal Editar Usuario
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [editFormData, setEditFormData] = useState({
    nombre: '',
    correo: '',
    role: 'usuario',
    is_active: true,
  });
  const [editError, setEditError] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

  // Modal Actividad de Usuario
  const [isActivityModalOpen, setIsActivityModalOpen] = useState(false);
  const [activityUser, setActivityUser] = useState(null);
  const [activityLogs, setActivityLogs] = useState([]);
  const [loadingActivity, setLoadingActivity] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Error al obtener la lista de usuarios.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleOpenCreateModal = () => {
    setNewUserData({
      nombre: '',
      correo: '',
      clave: '',
      role: 'usuario',
    });
    setCreateError('');
    setIsCreateModalOpen(true);
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (isCreating) return;
    setCreateError('');

    if (!newUserData.nombre.trim() || !newUserData.correo.trim() || !newUserData.clave) {
      setCreateError('Todos los campos son obligatorios.');
      return;
    }

    if (newUserData.clave.length < 6) {
      setCreateError('La clave debe tener al menos 6 caracteres.');
      return;
    }

    setIsCreating(true);
    try {
      await api.createUser({
        nombre: newUserData.nombre.trim(),
        correo: newUserData.correo.trim(),
        clave: newUserData.clave,
        confirmacion_clave: newUserData.clave,
        role: newUserData.role,
      });
      setSuccessMsg(`Usuario ${newUserData.correo} creado exitosamente con rol ${newUserData.role}.`);
      setIsCreateModalOpen(false);
      fetchUsers();
    } catch (err) {
      // Conservar nombre, correo y rol, pero limpiar la clave por seguridad
      setNewUserData((prev) => ({
        ...prev,
        clave: '',
      }));
      setCreateError(err.message || 'Error al crear usuario.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleOpenEditModal = (u) => {
    setEditingUser(u);
    setEditFormData({
      nombre: u.nombre,
      correo: u.correo,
      role: u.role,
      is_active: u.is_active,
    });
    setEditError('');
    setIsEditModalOpen(true);
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    setEditError('');

    setIsUpdating(true);
    try {
      await api.updateUser(editingUser.id, {
        nombre: editFormData.nombre.trim(),
        correo: editFormData.correo.trim(),
        role: editingUser.role === 'admin' ? undefined : editFormData.role,
        is_active: editFormData.is_active,
      });
      setSuccessMsg(`Usuario ${editingUser.correo} actualizado exitosamente.`);
      setIsEditModalOpen(false);
      fetchUsers();
    } catch (err) {
      setEditError(err.message || 'Error al actualizar usuario.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDeleteUser = async (u) => {
    if (u.id === user?.id) {
      alert('No puedes eliminar tu propia cuenta de administrador.');
      return;
    }

    if (!window.confirm(`¿Estás seguro de que deseas eliminar permanentemente a ${u.nombre} (${u.correo})? Se cerrarán todas sus sesiones.`)) {
      return;
    }

    try {
      await api.deleteUser(u.id);
      setSuccessMsg(`Usuario ${u.correo} eliminado exitosamente.`);
      fetchUsers();
    } catch (err) {
      setError(err.message || 'Error al eliminar usuario.');
    }
  };

  const handleViewActivity = async (u) => {
    setActivityUser(u);
    setIsActivityModalOpen(true);
    setLoadingActivity(true);
    try {
      const logs = await api.getUserActivity(u.id);
      setActivityLogs(Array.isArray(logs) ? logs : []);
    } catch (err) {
      setActivityLogs([]);
    } finally {
      setLoadingActivity(false);
    }
  };

  const filteredUsers = users.filter((u) => {
    const term = searchTerm.toLowerCase();
    return (
      u.nombre.toLowerCase().includes(term) ||
      u.correo.toLowerCase().includes(term) ||
      u.role.toLowerCase().includes(term)
    );
  });

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
            Gestión de Usuarios y Cuentas
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Administra los roles del sistema (Editor, Usuario), activa/desactiva cuentas y supervisa registros de auditoría.
          </p>
        </div>

        <button
          type="button"
          onClick={handleOpenCreateModal}
          className="btn btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <UserPlus size={18} />
          <span>Crear Nuevo Usuario</span>
        </button>
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
          placeholder="Buscar por nombre, correo o rol..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="form-control"
          style={{ paddingLeft: '2.5rem' }}
        />
      </div>

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Cargando usuarios...
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)' }}>Usuario</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)' }}>Correo</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)' }}>Rol</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)' }}>Estado</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)' }}>Registrado</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-muted)', textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => {
                  const isCurrent = u.id === user?.id;
                  let roleBadgeBg = '#f1f5f9';
                  let roleBadgeColor = '#475569';
                  let roleName = 'Usuario';

                  if (u.role === 'admin') {
                    roleBadgeBg = '#ede9fe';
                    roleBadgeColor = '#6d28d9';
                    roleName = 'Administrador';
                  } else if (u.role === 'editor') {
                    roleBadgeBg = '#e0f2fe';
                    roleBadgeColor = '#0369a1';
                    roleName = 'Editor';
                  }

                  return (
                    <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>
                        {u.nombre} {isCurrent && <span style={{ fontSize: '0.75rem', color: '#2563eb' }}>(Tú)</span>}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                        {u.correo}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{ padding: '0.2rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, background: roleBadgeBg, color: roleBadgeColor }}>
                          {roleName}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: u.is_active ? '#059669' : '#dc2626' }}>
                          {u.is_active ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                          <span>{u.is_active ? 'Activo' : 'Inactivo'}</span>
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/D'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            onClick={() => handleViewActivity(u)}
                            className="btn btn-secondary"
                            style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem' }}
                            title="Ver actividad"
                          >
                            <Activity size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenEditModal(u)}
                            className="btn btn-secondary"
                            style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem' }}
                            title="Editar usuario"
                          >
                            <Edit2 size={14} />
                          </button>
                          {!isCurrent && (
                            <button
                              type="button"
                              onClick={() => handleDeleteUser(u)}
                              className="btn btn-secondary"
                              style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', color: '#dc2626' }}
                              title="Eliminar usuario"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL CREAR USUARIO */}
      {isCreateModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '450px', width: '100%', background: '#ffffff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Crear Nuevo Usuario</h3>
              <button type="button" onClick={() => setIsCreateModalOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}>&times;</button>
            </div>

            {createError && (
              <div style={{ padding: '0.5rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.8rem' }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateUser}>
              <div style={{ marginBottom: '0.75rem' }}>
                <label className="form-label">Nombre Completo *</label>
                <input
                  type="text"
                  required
                  value={newUserData.nombre}
                  onChange={(e) => setNewUserData((p) => ({ ...p, nombre: e.target.value }))}
                  placeholder="Ej. Profesor Carlos Gómez"
                  className="form-control"
                />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label className="form-label">Correo Institucional *</label>
                <input
                  type="email"
                  required
                  value={newUserData.correo}
                  onChange={(e) => setNewUserData((p) => ({ ...p, correo: e.target.value }))}
                  placeholder="usuario@institucion.edu"
                  className="form-control"
                />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label className="form-label">Contraseña Temporal * (mínimo 6 caracteres)</label>
                <input
                  type="password"
                  required
                  value={newUserData.clave}
                  onChange={(e) => setNewUserData((p) => ({ ...p, clave: e.target.value }))}
                  className="form-control"
                />
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label className="form-label">Rol Permitido *</label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData((p) => ({ ...p, role: e.target.value }))}
                  className="form-control"
                >
                  <option value="usuario">Usuario (Estudiante / Evaluador: sube exámenes habilitados)</option>
                  <option value="editor">Editor (Profesor: crea y configura exámenes)</option>
                </select>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Nota de seguridad: Los administradores solo pueden crearse mediante la consola del servidor.
                </p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="btn btn-secondary" disabled={isCreating}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={isCreating}>
                  {isCreating ? 'Creando...' : 'Crear Usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL EDITAR USUARIO */}
      {isEditModalOpen && editingUser && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '450px', width: '100%', background: '#ffffff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Modificar Cuenta</h3>
              <button type="button" onClick={() => setIsEditModalOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}>&times;</button>
            </div>

            {editError && (
              <div style={{ padding: '0.5rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.8rem' }}>
                {editError}
              </div>
            )}

            <form onSubmit={handleUpdateUser}>
              <div style={{ marginBottom: '0.75rem' }}>
                <label className="form-label">Nombre Completo</label>
                <input
                  type="text"
                  required
                  value={editFormData.nombre}
                  onChange={(e) => setEditFormData((p) => ({ ...p, nombre: e.target.value }))}
                  className="form-control"
                />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label className="form-label">Correo Institucional</label>
                <input
                  type="email"
                  required
                  value={editFormData.correo}
                  onChange={(e) => setEditFormData((p) => ({ ...p, correo: e.target.value }))}
                  className="form-control"
                />
              </div>

              {editingUser.role !== 'admin' && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <label className="form-label">Rol</label>
                  <select
                    value={editFormData.role}
                    onChange={(e) => setEditFormData((p) => ({ ...p, role: e.target.value }))}
                    className="form-control"
                  >
                    <option value="usuario">Usuario</option>
                    <option value="editor">Editor</option>
                  </select>
                </div>
              )}

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={editFormData.is_active}
                    disabled={editingUser.id === user?.id}
                    onChange={(e) => setEditFormData((p) => ({ ...p, is_active: e.target.checked }))}
                  />
                  <span>Cuenta Activa (si se desmarca, se revocan todas sus sesiones y se bloquea el acceso)</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
                <button type="button" onClick={() => setIsEditModalOpen(false)} className="btn btn-secondary" disabled={isUpdating}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={isUpdating}>
                  {isUpdating ? 'Guardando...' : 'Guardar Cambios'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL ACTIVIDAD / AUDITORÍA DE USUARIO */}
      {isActivityModalOpen && activityUser && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '650px', width: '100%', maxHeight: '80vh', overflowY: 'auto', background: '#ffffff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Registro de Actividad</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>{activityUser.nombre} ({activityUser.correo})</p>
              </div>
              <button type="button" onClick={() => setIsActivityModalOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}>&times;</button>
            </div>

            {loadingActivity ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Cargando registros...</div>
            ) : activityLogs.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No hay eventos registrados para este usuario.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {activityLogs.map((log) => (
                  <div key={log.id} style={{ padding: '0.6rem 0.8rem', border: '1px solid #e2e8f0', borderRadius: '4px', background: '#f8fafc', fontSize: '0.8rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                      <span style={{ fontWeight: 600, color: '#1e293b' }}>{log.action}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{new Date(log.timestamp).toLocaleString()}</span>
                    </div>
                    {log.details && (
                      <div style={{ color: '#475569', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                        {JSON.stringify(log.details)}
                      </div>
                    )}
                    {log.ip_address && (
                      <div style={{ color: '#94a3b8', fontSize: '0.7rem', marginTop: '0.2rem' }}>IP: {log.ip_address}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

