import { useCallback, useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import ChatThread from "../components/ChatThread";
import { api } from "../lib/api";

export default function WorkspacePage() {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");

  const loadDocuments = useCallback(async () => {
    try {
      const res = await api.listDocuments();
      setDocuments(res.documents);
    } catch {
      // silently ignore transient failures; next poll will retry
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.listConversations();
      setConversations(res.conversations);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    loadConversations();
  }, [loadDocuments, loadConversations]);

  // Poll documents while any are still pending/processing, so status updates without a refresh.
  useEffect(() => {
    const hasActive = documents.some((d) => d.status === "pending" || d.status === "processing");
    if (!hasActive) return;
    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
  }, [documents, loadDocuments]);

  async function handleUpload(file) {
    setUploading(true);
    setUploadError("");
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteDocument(id);
      await loadDocuments();
    } catch (err) {
      setUploadError(err.message);
    }
  }

  async function handleRetry(id) {
    try {
      await api.reprocessDocument(id);
      await loadDocuments();
    } catch (err) {
      setUploadError(err.message);
    }
  }

  async function handleSelectConversation(id) {
    setActiveConversationId(id);
    setAskError("");
    try {
      const res = await api.getConversation(id);
      setMessages(res.messages);
    } catch (err) {
      setAskError(err.message);
    }
  }

  async function handleNewConversation() {
    try {
      const conv = await api.createConversation();
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      setMessages([]);
    } catch (err) {
      setAskError(err.message);
    }
  }

  async function handleAsk(question) {
    let conversationId = activeConversationId;

    // No conversation selected yet — create one on the fly.
    if (!conversationId) {
      try {
        const conv = await api.createConversation();
        setConversations((prev) => [conv, ...prev]);
        conversationId = conv.id;
        setActiveConversationId(conversationId);
      } catch (err) {
        setAskError(err.message);
        return;
      }
    }

    // Optimistically show the user's question right away.
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content: question, citations: [] },
    ]);

    setAsking(true);
    setAskError("");
    try {
      const assistantMessage = await api.askQuestion(conversationId, question);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setAskError(err.message);
    } finally {
      setAsking(false);
    }
  }

  const hasReadyDocuments = documents.some((d) => d.status === "ready");

  return (
    <div className="flex">
      <Sidebar
        documents={documents}
        onUpload={handleUpload}
        uploading={uploading}
        onDelete={handleDelete}
        onRetry={handleRetry}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <div className="flex-1 flex flex-col">
        {uploadError && (
          <p className="px-8 py-2 text-xs text-rust bg-rust/5 border-b border-stone-line">
            {uploadError}
          </p>
        )}
        {askError && (
          <p className="px-8 py-2 text-xs text-rust bg-rust/5 border-b border-stone-line">
            {askError}
          </p>
        )}
        <ChatThread
          messages={messages}
          onAsk={handleAsk}
          asking={asking}
          hasReadyDocuments={hasReadyDocuments}
        />
      </div>
    </div>
  );
}