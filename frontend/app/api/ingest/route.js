import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";
import { startIngestion } from "@/lib/ingestor";

// (Re)index a file that is already in S3, e.g. one uploaded before the ingestor existed.
export async function POST(request) {
  if (!getSessionUser(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { key } = await request.json().catch(() => ({}));
  if (!key) {
    return NextResponse.json({ error: "key is required" }, { status: 400 });
  }

  try {
    const doc = await startIngestion(key);
    return NextResponse.json({ ok: true, status: doc.status });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 502 });
  }
}
