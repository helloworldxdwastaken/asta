// ── Auth state management for multi-user Asta ─────────────────────────────────

export interface User {
  id: string;
  username: string;
  role: "admin" | "user";
}

const JWT_KEY = "asta_jwt";
const USER_KEY = "asta_user";

export function getJwt(): string | null {
  return localStorage.getItem(JWT_KEY);
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: User): void {
  localStorage.setItem(JWT_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(JWT_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAdmin(): boolean {
  return getStoredUser()?.role === "admin";
}
