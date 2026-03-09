// Platform-safe key-value storage
// Native: expo-secure-store, Web: localStorage
import { Platform } from "react-native";

export async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return localStorage.getItem(key);
  }
  const { getItemAsync } = await import("expo-secure-store");
  return getItemAsync(key);
}

export async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    localStorage.setItem(key, value);
    return;
  }
  const { setItemAsync } = await import("expo-secure-store");
  await setItemAsync(key, value);
}

export async function deleteItem(key: string): Promise<void> {
  if (Platform.OS === "web") {
    localStorage.removeItem(key);
    return;
  }
  const { deleteItemAsync } = await import("expo-secure-store");
  await deleteItemAsync(key);
}
