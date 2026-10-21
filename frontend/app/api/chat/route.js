import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(request) {
  if (!getSessionUser(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { message } = await request.json().catch(() => ({}));
  if (!message?.trim()) {
    return NextResponse.json({ error: "Message is required" }, { status: 400 });
  }

  // Forward to the Python backend, which calls the LLM.
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message.trim() }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = typeof data.detail === "string" ? data.detail : "Backend request failed";
      return NextResponse.json({ error }, { status: res.status });
    }
    return NextResponse.json({ reply: data.reply });
  } catch (err) {
    console.error(err);
    return NextResponse.json({ error: "Could not reach backend" }, { status: 502 });
  }
}
