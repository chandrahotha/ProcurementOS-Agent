// Demo token storage. Production replaces this with the OIDC session;
// the API already enforces membership server-side, so a pasted dev token
// can never reach across tenants.
"use client";

const KEY = "pos_token";

export function readToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(KEY) ?? "";
}

export function saveToken(token: string): void {
  window.localStorage.setItem(KEY, token);
}
