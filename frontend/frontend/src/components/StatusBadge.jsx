const STYLES = {
  pending: "text-ink-soft",
  processing: "text-brass",
  ready: "text-sage",
  failed: "text-rust",
};

const LABELS = {
  pending: "Queued",
  processing: "Processing…",
  ready: "Ready",
  failed: "Failed",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`text-xs ${STYLES[status] || "text-ink-soft"}`}>
      {LABELS[status] || status}
    </span>
  );
}
