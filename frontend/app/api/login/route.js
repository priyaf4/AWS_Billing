import { NextResponse } from "next/server";
import { createSession, SESSION_COOKIE, SESSION_MAX_AGE } from "@/lib/session";

export async function POST(request) {
  const { username, password } = await request.json().catch(() => ({}));

  const validUser = process.env.ADMIN_USERNAME || "admin";
  const validPass = process.env.ADMIN_PASSWORD || "admin";
  if (username !== validUser || password !== validPass) {
    return NextResponse.json({ error: "Invalid username or password" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, createSession(username), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}
