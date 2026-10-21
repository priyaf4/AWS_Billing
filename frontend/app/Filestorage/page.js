"use client";

import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileStoragePage() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const fileInputRef = useRef(null);

  async function loadFiles() {
    setLoading(true);
    try {
      const res = await fetch("/api/files");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setFiles(data.files);
      setError("");
    } catch (err) {
      setError(err.message || "Could not load files");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFiles();
  }, []);

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
      setMessage(`Uploaded "${selected.name}"`);
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
