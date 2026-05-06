import React, { useState, useEffect, useRef } from "react";

const SERVER_URL = "http://localhost:8001";

// ── helpers ───────────────────────────────────────────────────────────────────
const fmt = (ts) => {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
};

const severityColor = (text = "") => {
  const t = text.toUpperCase();
  if (t.includes("CRITICAL")) return "#ef4444";
  if (t.includes("HIGH"))     return "#f97316";
  if (t.includes("MEDIUM"))   return "#eab308";
  return "#22c55e";
};

// ── sub-components ────────────────────────────────────────────────────────────

const DetectionBadge = ({ det }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: "4px",
    padding: "3px 8px", borderRadius: "12px", fontSize: "0.75rem",
    fontWeight: "600", marginRight: "6px", marginBottom: "4px",
    background: det.class === "pot_hauler" ? "#fee2e2" : "#dbeafe",
    color:      det.class === "pot_hauler" ? "#b91c1c" : "#1d4ed8",
    border: `1px solid ${det.class === "pot_hauler" ? "#fca5a5" : "#93c5fd"}`,
  }}>
    {det.class === "pot_hauler" ? "🚛" : det.class === "person" ? "🧑" : "📦"}
    {" "}{det.class} {(det.conf * 100).toFixed(0)}%
  </span>
);

const ResponseBox = ({ title, color, icon, text, isLoading }) => (
  <div style={{
    flex: 1, background: "#0f172a", borderRadius: "10px",
    border: `1px solid ${color}40`, overflow: "hidden",
  }}>
    <div style={{
      padding: "10px 14px", background: `${color}18`,
      borderBottom: `1px solid ${color}30`,
      display: "flex", alignItems: "center", gap: "8px",
    }}>
      <span style={{ fontSize: "1.1rem" }}>{icon}</span>
      <span style={{ color, fontWeight: "700", fontSize: "0.85rem" }}>{title}</span>
    </div>
    <div style={{
      padding: "14px", fontSize: "0.82rem", color: "#cbd5e1",
      lineHeight: "1.65", minHeight: "160px",
      whiteSpace: "pre-wrap", wordBreak: "break-word",
    }}>
      {isLoading
        ? <span style={{ color: "#64748b", fontStyle: "italic" }}>⏳ Waiting for Gemma 3 27B…</span>
        : text || <span style={{ color: "#475569", fontStyle: "italic" }}>No response yet.</span>
      }
    </div>
  </div>
);

// ── main page ─────────────────────────────────────────────────────────────────

const VlmReasoningPage = () => {
  const [snapshots, setSnapshots]     = useState([]);
  const [history, setHistory]         = useState([]);
  const [selected, setSelected]       = useState(null);   // analysis result
  const [analyzing, setAnalyzing]     = useState(false);
  const [activeSnap, setActiveSnap]   = useState(null);   // snapshot being analyzed
  const [error, setError]             = useState(null);
  const pollRef = useRef(null);

  // ── load latest snapshots on mount + poll for new ones ──────────────────────
  useEffect(() => {
    fetchSnapshots();
    fetchHistory();
    pollRef.current = setInterval(() => {
      fetchSnapshots();
      fetchHistory();
    }, 5000);
    return () => clearInterval(pollRef.current);
  }, []);

  const fetchSnapshots = async () => {
    try {
      const r = await fetch(`${SERVER_URL}/latest_snapshots`);
      const d = await r.json();
      setSnapshots(d.snapshots || []);
    } catch (_) {}
  };

  const fetchHistory = async () => {
    try {
      const r = await fetch(`${SERVER_URL}/vlm_history`);
      const d = await r.json();
      setHistory(d);
    } catch (_) {}
  };

  // ── trigger analysis on a snapshot ──────────────────────────────────────────
  const analyzeSnapshot = async (snap) => {
    setAnalyzing(true);
    setActiveSnap(snap);
    setSelected(null);
    setError(null);

    try {
      const r = await fetch(`${SERVER_URL}/analyze_hazard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          snapshot_path: snap.path,
          camera_id:     snap.camera_id,
          detections:    [],          // YOLO detections not embedded in filename; backend infers from context
          zone_status:   "HAZARD",
          zone_reason:   "Triggered from snapshot — pot_hauler active in bay",
          source_camera: snap.camera_id,
        }),
      });
      const result = await r.json();
      if (result.error) { setError(result.error); }
      else {
        setSelected(result);
        fetchHistory();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const display = selected || (history.length > 0 ? history[0] : null);

  // ── render ────────────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100%",
      background: "#0a0f1e", color: "#e2e8f0", overflow: "hidden",
    }}>

      {/* ── Header ── */}
      <div style={{
        padding: "16px 24px", borderBottom: "1px solid #1e293b",
        background: "#0d1627",
      }}>
        <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700", color: "#f8fafc" }}>
          🧠 YOLO → VLM Hazard Reasoning
        </h2>
        <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "#64748b" }}>
          Stage 1: YOLO detects what is there &nbsp;→&nbsp; Stage 2: Gemma 3 27B reasons why it's dangerous
        </p>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* ── Left panel: snapshots + history ── */}
        <div style={{
          width: "230px", minWidth: "230px", background: "#0d1627",
          borderRight: "1px solid #1e293b", display: "flex",
          flexDirection: "column", overflow: "hidden",
        }}>
          {/* Recent snapshots */}
          <div style={{ padding: "12px 12px 6px", borderBottom: "1px solid #1e293b" }}>
            <div style={{ fontSize: "0.72rem", fontWeight: "700", color: "#475569",
              textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
              📸 Recent Hazard Snapshots
            </div>
            {snapshots.length === 0 ? (
              <div style={{ fontSize: "0.75rem", color: "#334155", padding: "8px 0" }}>
                No snapshots yet — start a camera stream to generate them.
              </div>
            ) : snapshots.map((snap, i) => (
              <button
                key={i}
                onClick={() => analyzeSnapshot(snap)}
                disabled={analyzing}
                style={{
                  width: "100%", textAlign: "left", padding: "7px 8px",
                  marginBottom: "4px", borderRadius: "6px", cursor: "pointer",
                  background: activeSnap?.filename === snap.filename ? "#1e3a5f" : "#111827",
                  border: `1px solid ${activeSnap?.filename === snap.filename ? "#3b82f6" : "#1e293b"}`,
                  color: "#cbd5e1", fontSize: "0.72rem",
                  opacity: analyzing ? 0.6 : 1,
                }}
              >
                <div style={{ fontWeight: "600", color: "#93c5fd" }}>
                  📷 Camera {snap.camera_id}
                </div>
                <div style={{ color: "#475569", marginTop: "2px", fontSize: "0.67rem" }}>
                  {snap.filename.replace(".jpg", "").split("_").slice(1).join(" ")}
                </div>
              </button>
            ))}
          </div>

          {/* Past analyses */}
          <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
            <div style={{ fontSize: "0.72rem", fontWeight: "700", color: "#475569",
              textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
              🕑 Past Analyses
            </div>
            {history.length === 0 ? (
              <div style={{ fontSize: "0.75rem", color: "#334155" }}>
                No analyses yet.
              </div>
            ) : history.map((item, i) => (
              <button
                key={i}
                onClick={() => setSelected(item)}
                style={{
                  width: "100%", textAlign: "left", padding: "7px 8px",
                  marginBottom: "4px", borderRadius: "6px", cursor: "pointer",
                  background: display?.id === item.id ? "#1e3a5f" : "#111827",
                  border: `1px solid ${display?.id === item.id ? "#3b82f6" : "#1e293b"}`,
                  color: "#cbd5e1", fontSize: "0.72rem",
                }}
              >
                <div style={{ fontWeight: "600", color: "#f87171" }}>
                  🔴 Camera {item.camera_id} — {item.zone_status}
                </div>
                <div style={{ color: "#475569", marginTop: "2px", fontSize: "0.67rem" }}>
                  {fmt(item.timestamp)}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* ── Main content ── */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

          {error && (
            <div style={{
              padding: "12px 16px", background: "#450a0a", border: "1px solid #7f1d1d",
              borderRadius: "8px", color: "#fca5a5", fontSize: "0.82rem", marginBottom: "16px",
            }}>
              ⚠️ {error}
            </div>
          )}

          {!display && !analyzing && (
            <div style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", height: "100%", gap: "16px",
              color: "#334155", textAlign: "center",
            }}>
              <div style={{ fontSize: "3rem" }}>🧠</div>
              <div style={{ fontSize: "1rem", fontWeight: "600", color: "#475569" }}>
                Select a snapshot to analyze
              </div>
              <div style={{ fontSize: "0.82rem", maxWidth: "360px", color: "#334155", lineHeight: "1.6" }}>
                When the YOLO system detects a hazard, snapshots are saved automatically.
                Click any snapshot on the left to run Gemma 3 27B — once without domain context
                (to show the gap) and once with full SDI plant context + CoT prompting.
              </div>
            </div>
          )}

          {(display || analyzing) && (
            <>
              {/* ── Event header ── */}
              <div style={{
                display: "flex", alignItems: "flex-start", gap: "16px",
                marginBottom: "20px", flexWrap: "wrap",
              }}>
                {/* Snapshot image */}
                <div style={{
                  width: "200px", minWidth: "200px", borderRadius: "8px",
                  overflow: "hidden", border: "1px solid #1e293b",
                  background: "#0f172a",
                }}>
                  <img
                    src={display?.snapshot_path
                      ? `${SERVER_URL}/${display.snapshot_path}`
                      : (activeSnap ? activeSnap.url : "")}
                    alt="Hazard snapshot"
                    style={{ width: "100%", display: "block" }}
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                  <div style={{
                    padding: "6px 8px", fontSize: "0.68rem", color: "#475569",
                    textAlign: "center",
                  }}>
                    YOLO-annotated snapshot
                  </div>
                </div>

                {/* Event metadata */}
                <div style={{ flex: 1, minWidth: "200px" }}>
                  <div style={{
                    display: "inline-block", padding: "4px 12px", borderRadius: "20px",
                    background: "#450a0a", color: "#f87171", fontWeight: "700",
                    fontSize: "0.8rem", marginBottom: "10px",
                  }}>
                    🔴 {display?.zone_status || "HAZARD"}
                  </div>

                  <div style={{ fontSize: "0.82rem", color: "#94a3b8", marginBottom: "8px" }}>
                    <strong style={{ color: "#e2e8f0" }}>Camera:</strong>{" "}
                    {display?.camera_id || activeSnap?.camera_id || "—"}
                    {display?.source_camera && display.source_camera !== display.camera_id && (
                      <span style={{ color: "#64748b" }}>
                        {" "}(equipment detected by Cam {display.source_camera})
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: "0.82rem", color: "#94a3b8", marginBottom: "8px" }}>
                    <strong style={{ color: "#e2e8f0" }}>YOLO reason:</strong>{" "}
                    {display?.zone_reason || "—"}
                  </div>

                  {display?.detections?.length > 0 && (
                    <div style={{ marginBottom: "8px" }}>
                      <div style={{ fontSize: "0.72rem", color: "#475569", marginBottom: "4px" }}>
                        DETECTIONS
                      </div>
                      {display.detections.map((d, i) => <DetectionBadge key={i} det={d} />)}
                    </div>
                  )}

                  <div style={{ fontSize: "0.72rem", color: "#334155" }}>
                    {fmt(display?.timestamp)}
                  </div>
                </div>
              </div>

              {/* ── Two-column VLM responses ── */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{
                  display: "flex", alignItems: "center", gap: "10px",
                  marginBottom: "12px",
                }}>
                  <div style={{
                    height: "1px", flex: 1, background: "#1e293b",
                  }} />
                  <span style={{ fontSize: "0.75rem", color: "#475569", whiteSpace: "nowrap" }}>
                    GEMMA 3 27B RESPONSES
                  </span>
                  <div style={{ height: "1px", flex: 1, background: "#1e293b" }} />
                </div>

                <div style={{ display: "flex", gap: "12px" }}>
                  <ResponseBox
                    title="WITHOUT domain context"
                    color="#f97316"
                    icon="⚠️"
                    text={display?.response_no_ctx}
                    isLoading={analyzing && !display?.response_no_ctx}
                  />
                  <ResponseBox
                    title="WITH SDI plant context + CoT"
                    color="#22c55e"
                    icon="✅"
                    text={display?.response_with_ctx}
                    isLoading={analyzing && !display?.response_with_ctx}
                  />
                </div>
              </div>

              {/* ── Callout explaining what this shows ── */}
              <div style={{
                padding: "12px 16px", background: "#0f172a",
                border: "1px solid #1e293b", borderRadius: "8px",
                fontSize: "0.78rem", color: "#64748b", lineHeight: "1.6",
              }}>
                <strong style={{ color: "#94a3b8" }}>What this demonstrates: </strong>
                The left response shows what a general-purpose VLM produces with no plant knowledge —
                often vague or focused on wrong hazards. The right response shows how domain-specific
                context + chain-of-thought prompting, combined with YOLO's grounded detections,
                produces actionable plant-specific safety reasoning. This is the core contribution
                of the two-stage pipeline.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default VlmReasoningPage;
