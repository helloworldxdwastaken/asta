import { getItem, setItem, deleteItem } from "./storage";
import type { User } from "./types";

const JWT_KEY = "asta_jwt";
const USER_KEY = "asta_user";

export async function getJwt(): Promise<string | null> {
  return getItem(JWT_KEY);
}

export async function setJwt(token: string): Promise<void> {
  await setItem(JWT_KEY, token);
}

export async function clearAuth(): Promise<void> {
  await deleteItem(JWT_KEY);
  await deleteItem(USER_KEY);
}

export async function getUser(): Promise<User | null> {
  const raw = await getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export async function setUser(user: User): Promise<void> {
  await setItem(USER_KEY, JSON.stringify(user));
}

export async function isAdmin(): Promise<boolean> {
  const u = await getUser();
  return u?.role === "admin";
}
