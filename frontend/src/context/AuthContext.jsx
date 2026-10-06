import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

const STORAGE_KEY = 'omrchecker_user';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem(STORAGE_KEY);
    if (!savedUser) return null;
    try {
      return JSON.parse(savedUser);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  });

  const [isLoading, setIsLoading] = useState(true);

  // Al montar, si hay token almacenado, verificar vigencia con el backend
  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    api.getMe()
      .then((userData) => {
        setUser(userData);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(userData));
      })
      .catch(() => {
        // Token inválido o expirado
        setUser(null);
        api.setToken(null);
        localStorage.removeItem(STORAGE_KEY);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const login = async (correo, clave) => {
    try {
      const response = await api.login({ correo, clave });
      api.setToken(response.token);
      setUser(response.user);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(response.user));
      return { success: true };
    } catch (err) {
      const msg = err && err.message ? String(err.message) : 'Error al iniciar sesión.';
      return {
        success: false,
        message: msg !== '[object Object]' ? msg : 'Error de autenticación.',
      };
    }
  };

  const register = async (userData) => {
    try {
      const response = await api.register(userData);
      return { success: true, user: response };
    } catch (err) {
      const msg = err && err.message ? String(err.message) : 'Error al registrar el usuario.';
      return {
        success: false,
        message: msg !== '[object Object]' ? msg : 'Error al registrar el usuario.',
      };
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      api.setToken(null);
      setUser(null);
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        register,
        logout,
        isAuthenticated: Boolean(user),
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe utilizarse dentro de AuthProvider');
  }
  return context;
}