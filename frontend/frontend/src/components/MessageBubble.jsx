function renderWithMarkers(content) {
  // Splits on [n] citation markers and renders them as small superscript footnote numbers.
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      return (
        <sup key={i} className="text-brass-dark font-medium mx-0.5">
          {match[1]}
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-prose ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-ink text-stone-bg"
              : message.is_answerable === false
              ? "bg-stone-card border border-stone-line text-ink-soft italic"
              : "bg-stone-card border border-stone-line text-ink"
          }`}
        >
          {isUser ? message.content : renderWithMarkers(message.content)}
        </div>

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1 text-left">
            {message.citations.map((c, i) => (
              <p key={c.id || i} className="text-xs text-ink-soft border-l-2 border-brass-soft pl-2">
                <span className="text-brass-dark font-medium">[{i + 1}]</span>{" "}
                {c.page_number ? `Page ${c.page_number} — ` : ""}
                {c.snippet}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
