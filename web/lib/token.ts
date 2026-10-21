// Session token storage. The token is minted by POST /auth/login from an
// email and a password; production replaces this with the OIDC session.
// The API enforces membership server-side, so a token can never reach
// across tenants.
"use client";

const KEY = "pos_token";

export function readToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(KEY) ?? "";
}

export function saveToken(token: string): void {
  window.localStorage.setItem(KEY, token);
}
