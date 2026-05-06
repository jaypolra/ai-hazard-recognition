import React, { useRef, useEffect, useState, useCallback } from "react";

const SERVER_URL = "http://localhost:8001";
const STATUS_POLL_MS = 1000;

const CameraFeed = ({
  cameraId,
  isSelected,
  onSelect,
  videoSrc,
  qualityHigh = false,
  sharpness = 1.0,
  gamma = 1.0,
  useDeepsort = false,
  syncTime = null,
}) => {
  const imgRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState(null);
  const [zoneState, setZoneState] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    if (imgRef.current) {
      const q = qualityHigh ? "high" : "low";
      imgRef.current.src =
        `${SERVER_URL}/stream_${cameraId}?quality=${q}` +
        `&sharpness=${sharpness}&gamma=${gamma}` +
        `&deepsort=${useDeepsort}&sync_time=${syncTime}`;
    }
  }, [cameraId, qualityHigh, sharpness, gamma, useDeepsort, syncTime]);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${SERVER_URL}/hazard_status`);
      const data = await r.json();
      if (data[cameraId]) setZoneState(data[cameraId]);
    } catch (_) {}
  }, [cameraId]);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, STATUS_POLL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleLoad  = () => setIsLoading(false);
  const handleError = () => { setError("Stream unavailable"); setIsLoading(false); };

  const isHazard  = zoneState?.is_hazard  ?? false;
  const isCaution = zoneState?.is_caution ?? false;
  const badgeBg   = isHazard ? "#dc2626" : isCaution ? "#d97706" : "#16a34a";
  const barBg     = isHazard ? "#1c0000"  : isCaution ? "#1c1000" : "#001208";
  const barBorder = isHazard ? "#7f1d1d"  : isCaution ? "#92400e" : "#14532d";
  const reasonTxt = zoneState?.reason ?? "Waiting for stream…";
  const reasonCol = isHazard ? "#fca5a5"  : isCaution ? "#fcd34d" : "#86efac";

  return (
    <div
      className={`camera-tile ${isSelected ? "selected" : ""}`}
      onClick={() => onSelect(cameraId)}
    >
      {/* ── Video feed ── */}
      <div className="camera-feed-area">
        {isLoading && (
          <div style={{ color: "#64748b", fontSize: "0.85rem" }}>
            {error || "Loading stream…"}
          </div>
        )}
        <img
          ref={imgRef}
          onLoad={handleLoad}
          onError={handleError}
          style={{ display: isLoading ? "none" : "block" }}
          alt={`Camera ${cameraId}`}
        />
      </div>

      {/* ── Status bar (bottom) ── */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 14px",
        background: barBg,
        borderTop: `1px solid ${barBorder}`,
        transition: "background 0.4s, border-color 0.4s",
        minHeight: "46px",
      }}>
        {/* Camera label */}
        <span style={{
          fontSize: "0.88rem", fontWeight: "800",
          color: "#cbd5e1", whiteSpace: "nowrap",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          Cam {cameraId}
        </span>

        {/* Badge */}
        <span style={{
          padding: "3px 12px", borderRadius: "4px",
          background: badgeBg, color: "#fff",
          fontWeight: "900", fontSize: "0.88rem",
          whiteSpace: "nowrap", letterSpacing: "0.05em",
        }}>
          {isHazard ? "⚠ HAZARD" : isCaution ? "~ CAUTION" : "✓ SAFE"}
        </span>

        {/* Reason */}
        <span style={{
          fontSize: "0.82rem", fontWeight: "600", color: reasonCol,
          flex: 1, overflow: "hidden",
          textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {reasonTxt}
        </span>

        {/* Live dot */}
        <span style={{
          width: "9px", height: "9px", borderRadius: "50%",
          background: zoneState ? "#22c55e" : "#475569",
          display: "inline-block", flexShrink: 0,
        }} />
      </div>
    </div>
  );
};

export default CameraFeed;
