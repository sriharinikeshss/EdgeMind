/**
 * AuthContext — Phase 1 JWT auth (M6).
 *
 * Provides login(), logout(), token, and currentUser to the whole app.
 * Stores the JWT in localStorage for page-refresh persistence.
 *
 * Phase 9: Replace the localStorage approach with Keycloak OIDC / HttpOnly cookies.
 */
import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface UserInfo {
  username: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: UserInfo | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('kavach_token')
  );
  const [user, setUser] = useState<UserInfo | null>(() => {
    const stored = localStorage.getItem('kavach_user');
    return stored ? (JSON.parse(stored) as UserInfo) : null;
  });

  const login = useCallback(async (username: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);

    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? 'Login failed');
    }

    const data = await res.json() as { access_token: string; username: string; role: string };
    localStorage.setItem('kavach_token', data.access_token);
    localStorage.setItem('kavach_user', JSON.stringify({ username: data.username, role: data.role }));
    setToken(data.access_token);
    setUser({ username: data.username, role: data.role });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('kavach_token');
    localStorage.removeItem('kavach_user');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
