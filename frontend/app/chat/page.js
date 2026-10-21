"use client";

import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";

export default function ChatPage() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! How can I help you today?" },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  // Set by the first reply; a page refresh clears it and starts a new conversation.
  const [conversationId, setConversationId] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversationId }),
      });
      const data = await res.json();
      if (res.ok && data.conversationId) setConversationId(data.conversationId);
      const reply = res.ok ? data.reply : `Error: ${data.error || "request failed"}`;
      setMessages((m) => [...m, { role: "assistant", text: reply }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Error: could not reach server" }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="page">
        <h1>Chat</h1>
        <div className="chat-box">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.text}
            </div>
          ))}
          {sending && <div className="bubble assistant muted">Typing...</div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-input" onSubmit={handleSend}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            aria-label="Message"
          />
          <button type="submit" disabled={sending || !input.trim()}>
            Send
          </button>
        </form>
      </main>
    </>
  );
}
