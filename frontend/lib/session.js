import crypto from "crypto";

export const SESSION_COOKIE = "session";
export const SESSION_MAX_AGE = 60 * 60 * 8; // 8 hours, in seconds

function secret() {
  return process.env.AUTH_SECRET || "dev-only-secret-change-me";
}

function sign(payload) {
  return crypto.createHmac("sha256", secret()).update(payload).digest("base64url");
}

export function createSession(username) {
  const payload = Buffer.from(
    JSON.stringify({ username, exp: Date.now() + SESSION_MAX_AGE * 1000 })
  ).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

// Returns the username for a valid, unexpired token, otherwise null.
export function verifySession(token) {
  if (!token) return null;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;

  const expected = Buffer.from(sign(payload));
  const actual = Buffer.from(sig);
  if (expected.length !== actual.length || !crypto.timingSafeEqual(expected, actual)) {
    return null;
  }

  try {
    const { username, exp } = JSON.parse(Buffer.from(payload, "base64url").toString());
    return Date.now() < exp ? username : null;
  } catch {
    return null;
  }
}

export function getSessionUser(request) {
  return verifySession(request.cookies.get(SESSION_COOKIE)?.value);
}
