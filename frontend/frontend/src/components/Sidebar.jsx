import { useRef, useState } from "react";
import StatusBadge from "./StatusBadge";
import { useAuth } from "../context/AuthContext";

export default function Sidebar({
  documents,
  onUpload,
  uploading,
  onDelete,
  onRetry,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const { user, signOut } = useAuth();

  function handleFiles(files) {
    if (files && files[0]) onUpload(files[0]);
  }

  return (
    <aside className="w-72 shrink-0 border-r border-stone-line bg-stone-card flex flex-col h-screen">
      <div className="px-5 py-5 border-b border-stone-line">
        <p className="font-serif text-xl text-ink">Ask My Docs</p>
      </div>

      {/* Upload zone */}
      <div className="px-5 py-4 border-b border-stone-line">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer border border-dashed px-3 py-4 text-center transition-colors ${
            dragOver ? "border-brass bg-brass-soft/30" : "border-stone-line"
          }`}
        >
          <p className="text-xs text-ink-soft">
            {uploading ? "Uploading…" : "Drop a document, or click to browse"}
          </p>
          <p className="mt-1 text-[11px] text-ink-soft/70">PDF, DOCX or TXT</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Document list */}
      <div className="px-5 py-4 border-b border-stone-line overflow-y-auto max-h-56">
        <p className="text-[11px] text-ink-soft mb-2">Documents</p>
        {documents.length === 0 && (
          <p className="text-xs text-ink-soft/70">No documents uploaded yet.</p>
        )}
        <ul className="space-y-2">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-2">
              <span
                className="text-sm text-ink truncate"
                title={doc.status === "failed" ? doc.error_message : doc.file_name}
              >
                {doc.file_name}
              </span>
              <div className="flex items-center gap-2 shrink-0">
                <StatusBadge status={doc.status} />
                {doc.status === "failed" && (
                  <button
                    onClick={() => onRetry(doc.id)}
                    className="text-xs text-brass-dark hover:text-brass transition-colors"
                  >
                    Retry
                  </button>
                )}
                <button
                  onClick={() => onDelete(doc.id)}
                  className="text-xs text-ink-soft hover:text-rust transition-colors"
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Conversations */}
      <div className="px-5 py-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] text-ink-soft">Conversations</p>
          <button
            onClick={onNewConversation}
            className="text-xs text-brass-dark hover:text-brass transition-colors"
          >
            + New
          </button>
        </div>
        <ul className="space-y-1">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => onSelectConversation(c.id)}
                className={`w-full text-left text-sm truncate px-2 py-1.5 transition-colors ${
                  c.id === activeConversationId
                    ? "bg-brass-soft/50 text-ink"
                    : "text-ink-soft hover:bg-stone-bg"
                }`}
              >
                {c.title || "Untitled conversation"}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* User footer */}
      <div className="px-5 py-4 border-t border-stone-line flex items-center justify-between">
        <span className="text-xs text-ink-soft truncate">{user?.email}</span>
        <button
          onClick={signOut}
          className="text-xs text-ink-soft hover:text-rust transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}