/**
 * api.js - Servicio centralizado para comunicación con el backend FastAPI de OMRChecker.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const TOKEN_KEY = 'omrchecker_token';

/**
 * Retorna las cabeceras con el token de autorización Bearer si existe.
 */
function getAuthHeaders(extraHeaders = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = { ...extraHeaders };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Manejador estándar de respuestas HTTP para lanzar errores claros con el detalle de FastAPI.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `Error HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorDetail = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        // Errores de validación estructurados de FastAPI: [{ loc, msg, type }]
        const fieldLabels = {
          nombre: 'El nombre completo',
          name: 'El nombre completo',
          correo: 'El correo electrónico',
          email: 'El correo electrónico',
          clave: 'La contraseña',
          password: 'La contraseña',
          confirmacion_clave: 'La confirmación de contraseña',
          password_confirmation: 'La confirmación de contraseña',
          role: 'El rol',
        };

        const messages = errorData.detail
          .map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
              const field = Array.isArray(item.loc) && item.loc.length > 0
                ? String(item.loc[item.loc.length - 1])
                : '';
              const label = fieldLabels[field] || (field ? `El campo "${field}"` : 'El campo');
              const rawMsg = (item.msg || '').replace(/^Value error,\s*/i, '').trim();

              if (item.type === 'missing' || rawMsg.toLowerCase() === 'field required') {
                return `${label} es obligatorio.`;
              }
              if (item.type === 'string_too_short' || rawMsg.toLowerCase().includes('at least')) {
                return `${label} debe tener al menos 6 caracteres.`;
              }
              if (rawMsg) {
                return rawMsg.endsWith('.') ? rawMsg : `${rawMsg}.`;
              }
              return `${label} es inválido.`;
            }
            return '';
          })
          .filter(Boolean);

        errorDetail = messages.join(' ') || (errorData.message || 'Error de validación en los datos enviados.');
      } else if (errorData.message && typeof errorData.message === 'string') {
        errorDetail = errorData.message;
      } else if (errorData.detail && typeof errorData.detail === 'object') {
        errorDetail = errorData.detail.msg || JSON.stringify(errorData.detail);
      } else if (typeof errorData === 'object' && errorData !== null) {
        errorDetail = errorData.error || errorData.msg || JSON.stringify(errorData);
      }
    } catch {
      errorDetail = (await response.text()) || errorDetail;
    }

    if (typeof errorDetail !== 'string' || errorDetail === '[object Object]') {
      errorDetail = `Error en la solicitud (código ${response.status})`;
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  /**
   * Administrar token en localStorage
   */
  setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  /**
   * Registro de usuario en FastAPI
   */
  async register(data) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  /**
   * Inicio de sesión en FastAPI
   */
  async login(credentials) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });
    return handleResponse(res);
  },

  /**
   * Cierre de sesión en FastAPI
   */
  async logout() {
    try {
      const res = await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      return handleResponse(res);
    } catch {
      return { message: 'Sesión cerrada' };
    } finally {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  /**
   * Obtener perfil del usuario autenticado
   */
  async getMe() {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Comprobar estado de salud del backend.
   */
  async getHealth() {
    const res = await fetch(`${API_BASE.replace('/api', '')}/api/health`);
    return handleResponse(res);
  },

  /**
   * Enviar hojas OMR, template y evaluation para procesar.
   * @param {FormData} formData
   */
  async processOMR(formData) {
    const res = await fetch(`${API_BASE}/omr/process`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    return handleResponse(res);
  },

  /**
   * Obtener historial de exámenes del usuario autenticado.
   */
  async getHistory() {
    const res = await fetch(`${API_BASE}/omr/history`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Obtener estado general del trabajo (job).
   * @param {string} jobId
   */
  async getJobSummary(jobId) {
    const res = await fetch(`${API_BASE}/omr/jobs/${jobId}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Obtener resultados estructurados completos de un trabajo.
   * @param {string} jobId
   */
  async getJobResults(jobId) {
    const res = await fetch(`${API_BASE}/omr/jobs/${jobId}/results`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Obtener lista de imágenes procesadas de un trabajo.
   * @param {string} jobId
   */
  async getJobFiles(jobId) {
    const res = await fetch(`${API_BASE}/omr/jobs/${jobId}/files`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Reintentar procesamiento de un examen con un archivo ZIP de hojas corregidas.
   * @param {string} jobId
   * @param {FormData} formData
   */
  async retryJob(jobId, formData) {
    const res = await fetch(`${API_BASE}/omr/jobs/${jobId}/retry`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    return handleResponse(res);
  },

  /**
   * Obtener lista de plantillas disponibles en el backend.
   */
  async getTemplates() {
    try {
      const res = await fetch(`${API_BASE}/templates`, {
        headers: getAuthHeaders(),
      });
      return handleResponse(res);
    } catch {
      return [];
    }
  },

  /**
   * URL directa para visualización de imagen procesada con detecciones OMR.
   */
  getImageUrl(jobId, filename) {
    return `${API_BASE}/omr/jobs/${jobId}/image/${filename}`;
  },

  /**
   * URL directa para visualización de imagen original (inputs).
   */
  getOriginalImageUrl(jobId, filename) {
    return `${API_BASE}/omr/jobs/${jobId}/original-image/${filename}`;
  },

  /**
   * URL de descarga de CSV compatible con OMRChecker.
   */
  getExportCsvUrl(jobId) {
    return `${API_BASE}/omr/jobs/${jobId}/export/csv`;
  },

  /**
   * URL de descarga de Excel (.xlsx con openpyxl).
   */
  getExportExcelUrl(jobId) {
    return `${API_BASE}/omr/jobs/${jobId}/export/excel`;
  },

  /**
   * Descargar archivo con nombre automático desde el navegador.
   */
  async downloadFile(url, defaultFilename) {
    const res = await fetch(url, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('No se pudo descargar el archivo.');

    let filename = defaultFilename;
    const disposition = res.headers.get('content-disposition');
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename=["']?([^"']+)["']?/);
      if (match && match[1]) filename = match[1];
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  },

  /**
   * ==========================================
   * GESTIÓN DE EXÁMENES (RBAC)
   * ==========================================
   */
  async getExams() {
    const res = await fetch(`${API_BASE}/exams`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async getExam(examId) {
    const res = await fetch(`${API_BASE}/exams/${examId}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async createExam(examData) {
    const res = await fetch(`${API_BASE}/exams`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(examData),
    });
    return handleResponse(res);
  },

  async updateExam(examId, examData) {
    const res = await fetch(`${API_BASE}/exams/${examId}`, {
      method: 'PUT',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(examData),
    });
    return handleResponse(res);
  },

  async deleteExam(examId) {
    const res = await fetch(`${API_BASE}/exams/${examId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async assignExam(examId, userIds) {
    const res = await fetch(`${API_BASE}/exams/${examId}/assign`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ user_ids: userIds }),
    });
    return handleResponse(res);
  },

  async getExamAssignments(examId) {
    const res = await fetch(`${API_BASE}/exams/${examId}/assignments`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async unassignExam(examId, userId) {
    const res = await fetch(`${API_BASE}/exams/${examId}/assignments/${userId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * ==========================================
   * GESTIÓN DE USUARIOS (ROL ADMIN)
   * ==========================================
   */
  async getUsers() {
    const res = await fetch(`${API_BASE}/users`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async createUser(userData) {
    const res = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(userData),
    });
    return handleResponse(res);
  },

  async updateUser(userId, userData) {
    const res = await fetch(`${API_BASE}/users/${userId}`, {
      method: 'PUT',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(userData),
    });
    return handleResponse(res);
  },

  async deleteUser(userId) {
    const res = await fetch(`${API_BASE}/users/${userId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async getUserActivity(userId) {
    const res = await fetch(`${API_BASE}/users/${userId}/activity`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * ==========================================
   * PANEL GLOBAL ADMINISTRADOR
   * ==========================================
   */
  async getAdminStats() {
    const res = await fetch(`${API_BASE}/admin/stats`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  async getAuditLogs(limit = 100) {
    const res = await fetch(`${API_BASE}/admin/audit-logs?limit=${limit}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },
};
