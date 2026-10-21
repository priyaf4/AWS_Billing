"use client";

import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const IN_PROGRESS = ["pending", "processing"];

function RagStatus({ rag, onIndex, busy }) {
  switch (rag?.status) {
    case "ready":
      return <span className="success">Ready ({rag.chunks} chunks)</span>;
    case "pending":
    case "processing":
      return <span className="muted">Indexing...</span>;
    case "failed":
      return (
        <>
          <span className="error" title={rag.error}>Failed: {rag.error}</span>{" "}
          <button className="secondary" onClick={onIndex} disabled={busy}>Retry</button>
        </>
      );
    case "not_indexed":
      return (
        <button className="secondary" onClick={onIndex} disabled={busy}>Index</button>
      );
    case "superseded":
      return <span className="muted">Older copy (newer upload is used)</span>;
    default:
      return <span className="muted">Ingestor offline</span>;
  }
}

export default function FileStoragePage() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [indexing, setIndexing] = useState(null); // key of the file being sent for indexing
  const fileInputRef = useRef(null);

  // `quiet` refreshes in the background without the "Loading..." flicker
  async function loadFiles({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    try {
      const res = await fetch("/api/files");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setFiles(data.files);
      setError("");
    } catch (err) {
      setError(err.message || "Could not load files");
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => {
    loadFiles();
  }, []);

  // While any file is still being indexed, check again every 3 seconds
  const anyInProgress = files.some((f) => IN_PROGRESS.includes(f.rag?.status));
  useEffect(() => {
    if (!anyInProgress) return;
    const timer = setInterval(() => loadFiles({ quiet: true }), 3000);
    return () => clearInterval(timer);
  }, [anyInProgress]);

  async function handleIndex(file) {
    setIndexing(file.key);
    setError("");
    try {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: file.key }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      await loadFiles({ quiet: true });
    } catch (err) {
      setError(`Could not index "${file.name}": ${err.message}`);
    } finally {
      setIndexing(null);
    }
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!selected) return;

    setUploading(true);
    setError("");
    setMessage("");

    const form = new FormData();
    form.append("file", selected);

    try {
      const res = await fetch("/api/files", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setMessage(
        data.indexing
          ? `Uploaded "${selected.name}". Indexing it for the chat...`
          : `Uploaded "${selected.name}", but indexing could not start (${data.indexError}). Use "Index" to retry.`
      );
      setSelected(null);
      fileInputRef.current.value = "";
      await loadFiles();
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="page">
        <h1>File Storage</h1>

        <form className="panel upload" onSubmit={handleUpload}>
          <input
            ref={fileInputRef}
            type="file"
            onChange={(e) => setSelected(e.target.files[0] ?? null)}
            aria-label="Choose file"
          />
          <button type="submit" disabled={!selected || uploading}>
            {uploading ? "Uploading..." : "Upload to S3"}
          </button>
        </form>

        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}

        <div className="panel">
          <div className="panel-header">
            <h2>Uploaded files</h2>
            <button className="secondary" onClick={loadFiles} disabled={loading}>
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="muted">Loading...</p>
          ) : files.length === 0 ? (
            <p className="muted">No files uploaded yet.</p>
          ) : (
            <table className="file-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Knowledge base</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.key}>
                    <td>
                      <a href={f.url} target="_blank" rel="noopener noreferrer">
                        {f.name}
                      </a>
                    </td>
                    <td>{formatSize(f.size)}</td>
                    <td>{new Date(f.lastModified).toLocaleString()}</td>
                    <td>
                      <RagStatus
                        rag={f.rag}
                        onIndex={() => handleIndex(f)}
                        busy={indexing === f.key}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  );
}
