import type { Person, SessionTokens } from "@/lib/types";

const SESSION_KEY = "rcos.session";
const PERSON_KEY = "rcos.person";

export function loadSession(): SessionTokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as SessionTokens;
    if (!parsed.access_token || !parsed.refresh_token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session: SessionTokens) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  markSignedIn();
}

export function loadPerson(): Person | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PERSON_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Person;
  } catch {
    return null;
  }
}

export function savePerson(person: Person | null) {
  if (!person) {
    window.localStorage.removeItem(PERSON_KEY);
    return;
  }
  window.localStorage.setItem(PERSON_KEY, JSON.stringify(person));
}

export function clearSession() {
  window.localStorage.removeItem(SESSION_KEY);
  window.localStorage.removeItem(PERSON_KEY);
  markSignedOut();
}

export function markSignedIn() {
  document.cookie = "rcos_auth=1; Path=/; Max-Age=2592000; SameSite=Lax";
}

export function markSignedOut() {
  document.cookie = "rcos_auth=; Path=/; Max-Age=0; SameSite=Lax";
}
