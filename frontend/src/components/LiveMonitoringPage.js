import React, { useState, useEffect, useCallback } from "react";
import CameraFeed from "./CameraFeed";
import SingleCameraView from "./SingleCameraView";
import VideoUpload from "./VideoUpload";

const SERVER_URL = "http://localhost:8001";

// ── Blocker definitions ────────────────────────────────────────────────────────
const BLOCKER_DEFS = [
  { key: "far_north",   label: "Far North",   short: "FN" },
  { key: "inner_north", label: "Inner North",  short: "IN" },
  { key: "inner_south", label: "Inner South",  short: "IS" },
  { key: "far_south",   label: "Far South",    short: "FS" },
];

const ZONE_DEFS = [
  { key: "A", label: "Zone A", sub: "North",  b1: "far_north",   b2: "inner_north", cams: [1] },
  { key: "B", label: "Zone B", sub: "Middle", b1: "inner_north", b2: "inner_south", cams: [2, 3] },
  { key: "C", label: "Zone C", sub: "South",  b1: "inner_south", b2: "far_south",   cams: [4] },
];

// ── Small toggle switch component ─────────────────────────────────────────────
const Toggle = ({ on, onChange, disabled }) => (
  <div
    onClick={disabled ? undefined : onChange}
    style={{
      width: "36px", height: "20px", borderRadius: "10px",
      background: on ? "#16a34a" : "#475569",
      position: "relative", cursor: disabled ? "wait" : "pointer",
      transition: "background 0.2s", flexShrink: 0,
    }}
  >
    <div style={{
      position: "absolute", top: "2px",
      left: on ? "18px" : "2px",
      width: "16px", height: "16px", borderRadius: "50%",
      background: "#fff", transition: "left 0.2s",
      boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
    }} />
  </div>
);

// ── Zone isolation badge ───────────────────────────────────────────────────────
const ZoneBadge = ({ zone, blockers, liveStates, onConfirmClear }) => {
  const b1 = blockers[zone.b1];
  const b2 = blockers[zone.b2];
  const isolated = b1 && b2;
  const partial  = b1 || b2;

  // Zone memory: any camera in this zone has seen a vehicle and not confirmed clear
  const memoryActive = zone.cams.some(c => liveStates[c]?.memory_active);

  // If isolated + memory active → override badge to warn about blind spot
  const effectiveIsolated = isolated && !memoryActive;
  const bg     = effectiveIsolated ? "#dcfce7" : isolated && memoryActive ? "#fef3c7" : partial ? "#fef9c3" : "#fee2e2";
  const border = effectiveIsolated ? "#16a34a" : isolated && memoryActive ? "#d97706" : partial ? "#ca8a04" : "#dc2626";
  const color  = effectiveIsolated ? "#15803d" : isolated && memoryActive ? "#92400e" : partial ? "#92400e" : "#991b1b";
  const icon   = effectiveIsolated ? "✓" : isolated && memoryActive ? "⚠" : partial ? "~" : "✗";
  const status = effectiveIsolated ? "ISOLATED" : isolated && memoryActive ? "BLIND SPOT" : partial ? "PARTIAL" : "OPEN";

  return (
    <div style={{
      padding: "8px 14px", borderRadius: "8px",
      background: bg, border: `2px solid ${border}`,
      display: "flex", flexDirection: "column", gap: "4px",
      minWidth: "120px", transition: "all 0.3s",
    }}>
      <div style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: "700",
        textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {zone.label} · {zone.sub}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span style={{ fontSize: "0.92rem", fontWeight: "800", color }}>{icon} {status}</span>
      </div>
      <div style={{ fontSize: "0.72rem", color: "#64748b", fontWeight: "500" }}>
        Cam {zone.cams.join("+")} · {zone.b1.replace("_", " ")} + {zone.b2.replace("_", " ")}
      </div>
      {/* Confirm Zone Clear button — only shown when zone isolated + memory active */}
      {isolated && memoryActive && (
        <button
          onClick={(e) => { e.stopPropagation(); onConfirmClear(zone.key); }}
          style={{
            marginTop: "4px", padding: "4px 8px", borderRadius: "5px",
            background: "#dc2626", color: "#fff", border: "none",
            fontSize: "0.7rem", fontWeight: "700", cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          ✓ Confirm Zone Clear
        </button>
      )}
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const LiveMonitoringPage = ({ videoSrc, onVideoUpload }) => {
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [syncTime]                           = useState(Date.now());
  const [qualityHigh]                        = useState(false);
  const [sharpness]                          = useState(1.0);
  const [gamma]                              = useState(1.0);
  const [useDeepsort]                        = useState(false);
  const [blockers, setBlockers]              = useState({
    far_north: false, inner_north: false, inner_south: false, far_south: false,
  });
  const [loading, setLoading]     = useState({});
  const [liveStates, setLiveStates] = useState({});

  // Sync blocker state from backend on mount
  useEffect(() => {
    fetch(`${SERVER_URL}/blockers_status`)
      .then(r => r.json())
      .then(d => { if (d.blockers) setBlockers(d.blockers); })
      .catch(() => {});
  }, []);

  // Poll hazard status to get memory_active flags per camera
  useEffect(() => {
    const poll = () => {
      fetch(`${SERVER_URL}/hazard_status`)
        .then(r => r.json())
        .then(d => setLiveStates(d))
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 1500);
    return () => clearInterval(id);
  }, []);

  const handleConfirmClear = useCallback(async (zoneKey) => {
    try {
      await fetch(`${SERVER_URL}/confirm_zone_clear/${zoneKey}`, { method: "POST" });
    } catch (_) {}
  }, []);

  const handleBlockerToggle = useCallback(async (key) => {
    const next = !blockers[key];
    setLoading(l => ({ ...l, [key]: true }));
    try {
      await fetch(`${SERVER_URL}/set_blocker`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blocker: key, confirmed: next }),
      });
      setBlockers(b => ({ ...b, [key]: next }));
    } catch (_) {}
    setLoading(l => ({ ...l, [key]: false }));
  }, [blockers]);

  const handleCameraSelect = (cameraId) => {
    if (videoSrc) setSelectedCamera(cameraId);
  };

  if (selectedCamera !== null && videoSrc) {
    return (
      <SingleCameraView
        selectedCameraId={selectedCamera}
        onBackToGrid={() => setSelectedCamera(null)}
        onSwitchCamera={(cameraId) => setSelectedCamera(cameraId)}
        videoSrc={videoSrc} qualityHigh={qualityHigh}
        sharpness={sharpness} gamma={gamma}
        useDeepsort={useDeepsort} syncTime={syncTime}
      />
    );
  }

  if (!videoSrc) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div className="monitoring-toolbar"><h2>📺 Multi-Camera Live Monitoring</h2></div>
        <div style={{ flex: 1, padding: "2rem", overflow: "auto" }}>
          <VideoUpload onUpload={onVideoUpload} />
        </div>
      </div>
    );
  }

  const anyBlockerOn   = Object.values(blockers).some(Boolean);
  const allIsolated    = ZONE_DEFS.every(z => blockers[z.b1] && blockers[z.b2]);

  return (
    <div className="live-monitoring-page">
      <div className="monitoring-toolbar">
        <h2>📺 Multi-Camera Live Monitoring</h2>
        <p>Click any camera to view in full screen</p>
      </div>

      {/* ── Status legend ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: "20px", flexWrap: "wrap",
        padding: "8px 16px", marginBottom: "8px",
        background: "#f0f4f8", borderRadius: "8px", fontSize: "13px",
        border: "1px solid #e4e8f0",
      }}>
        {[
          { color: "#16a34a", label: "GREEN", desc: "Zone isolated or bay idle with blockers" },
          { color: "#d97706", label: "AMBER", desc: "Bay idle — no blockers set" },
          { color: "#dc2626", label: "RED",   desc: "Equipment active or person in unguarded zone" },
        ].map(({ color, label, desc }) => (
          <span key={label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "13px", height: "13px", borderRadius: "3px",
              background: color, display: "inline-block", flexShrink: 0 }}/>
            <span style={{ color: "#1a202c", fontWeight: "500" }}>
              <strong style={{ color }}>{label}</strong> — {desc}
            </span>
          </span>
        ))}
      </div>

      {/* ── Blocker control + zone summary row ── */}
      <div style={{
        display: "flex", gap: "12px", marginBottom: "8px", flexWrap: "wrap",
      }}>

        {/* Blocker toggles */}
        <div style={{
          background: "#f8fafc", border: "1px solid #e4e8f0", borderRadius: "10px",
          padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px",
          minWidth: "260px",
        }}>
          <div style={{ fontSize: "0.8rem", fontWeight: "700", color: "#475569",
            textTransform: "uppercase", letterSpacing: "0.08em" }}>
            🔒 Physical Blocker Status
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {BLOCKER_DEFS.map(({ key, label }) => (
              <div key={key} style={{
                display: "flex", alignItems: "center", gap: "8px",
                padding: "6px 12px", borderRadius: "6px",
                background: blockers[key] ? "#dcfce7" : "#f1f5f9",
                border: `1px solid ${blockers[key] ? "#16a34a" : "#cbd5e1"}`,
                transition: "all 0.2s",
              }}>
                <span style={{
                  fontSize: "0.85rem", fontWeight: "700",
                  color: blockers[key] ? "#15803d" : "#64748b",
                  whiteSpace: "nowrap",
                }}>
                  {label}
                </span>
                <Toggle
                  on={blockers[key]}
                  onChange={() => handleBlockerToggle(key)}
                  disabled={loading[key]}
                />
              </div>
            ))}
          </div>
          {anyBlockerOn && (
            <div style={{ fontSize: "0.78rem", fontWeight: "600", color: "#475569" }}>
              {allIsolated
                ? "✅ All zones isolated — full bay protection active"
                : "⚠ Partial blockers — some zones remain unguarded"}
            </div>
          )}
        </div>

        {/* Zone isolation summary */}
        <div style={{
          background: "#f8fafc", border: "1px solid #e4e8f0", borderRadius: "10px",
          padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px",
          flex: 1,
        }}>
          <div style={{ fontSize: "0.8rem", fontWeight: "700", color: "#475569",
            textTransform: "uppercase", letterSpacing: "0.08em" }}>
            📍 Zone Isolation Status
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {ZONE_DEFS.map(zone => (
              <ZoneBadge key={zone.key} zone={zone} blockers={blockers}
                liveStates={liveStates} onConfirmClear={handleConfirmClear} />
            ))}
          </div>
        </div>
      </div>

      {/* ── Camera grid ── */}
      <div className="camera-grid-4">
        {[1, 2, 3, 4].map((cameraId) => (
          <CameraFeed
            key={cameraId}
            cameraId={cameraId}
            isSelected={selectedCamera === cameraId}
            onSelect={handleCameraSelect}
            videoSrc={videoSrc[cameraId]}
            qualityHigh={qualityHigh}
            sharpness={sharpness}
            gamma={gamma}
            useDeepsort={useDeepsort}
            syncTime={syncTime}
          />
        ))}
      </div>
    </div>
  );
};

export default LiveMonitoringPage;
