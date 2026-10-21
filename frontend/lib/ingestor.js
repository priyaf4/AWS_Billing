// Server-side helpers for the RAG ingestor microservice (see ../ingestor).
const INGESTOR_URL = process.env.INGESTOR_URL || "http://localhost:8002";

async function ingestorFetch(path, options = {}) {
  const res = await fetch(`${INGESTOR_URL}/api/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : `Ingestor error ${res.status}`);
  }
  return data;
}

// Queue an uploaded S3 file for indexing. Returns the document record (status "pending").
export function startIngestion(key) {
  return ingestorFetch("/ingest", { method: "POST", body: JSON.stringify({ s3_key: key }) });
}

// Every file the ingestor knows about, with its status.
export async function listDocuments() {
  return (await ingestorFetch("/documents")).documents;
}
