import React, { useState, useRef, useEffect } from "react";
import {
  uploadVideo,
  setPolygon as sendPolygons,
  setConfidence
} from "../api";

const SERVER_URL = "http://localhost:8001";

const zoneTypes = {
  "Red Zone": "red",
  "Orange Zone": "orange",
  "Green Zone": "green",
};

function generateRegularPolygon(sides, width = 640, height = 480, radius = 100) {
  const angleStep = (2 * Math.PI) / sides;
  const centers = {
    3: [width * 0.25, height * 0.3],
    4: [width * 0.75, height * 0.3],
    5: [width * 0.25, height * 0.7],
    6: [width * 0.5, height * 0.5],
    7: [width * 0.75, height * 0.7],
  };
  const [cx, cy] = centers[sides] || [width / 2, height / 2];
  const points = [];

  for (let i = 0; i < sides; i++) {
    const angle = i * angleStep - Math.PI / 2;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    points.push([x, y]);
  }

  return points;
}

const StreamCard = ({ streamId, videoUploaded, setVideoUploaded }) => {
  const [polygons, setPolygons] = useState([]);
  const [appliedPolygons, setAppliedPolygons] = useState([]);
  const [selectedPolygon, setSelectedPolygon] = useState(null);
  const [dragIndex, setDragIndex] = useState(null);
  const [isDraggingPolygon, setIsDraggingPolygon] = useState(false);
  const [dragOffset, setDragOffset] = useState([0, 0]);
  const [zoneType, setZoneType] = useState("Red Zone");
  const [shapePoints, setShapePoints] = useState(6);
  const [confidence, setConfidenceVal] = useState(0.5);
  const [qualityHigh, setQualityHigh] = useState(false);
  const [sharpness, setSharpness] = useState(1.0);
  const [gamma, setGamma] = useState(1.0);
  const [backgroundUrl, setBackgroundUrl] = useState(null);
  const [useDeepsort, setUseDeepsort] = useState(false);
  const [videoSource, setVideoSource] = useState("video_1.mp4");

  // 🔶 Fullscreen state/refs
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const onFsChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  const enterFullscreen = async () => {
    if (!containerRef.current) return;
    try {
      await containerRef.current.requestFullscreen();
    } catch (e) {
      console.warn("Fullscreen request failed:", e);
    }
  };

  const exitFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
    } catch (e) {
      console.warn("Exit fullscreen failed:", e);
    }
  };

  const toggleFullscreen = () => {
    if (isFullscreen) exitFullscreen();
    else enterFullscreen();
  };

  const getStreamURL = () => {
    const basePath = videoSource === "webcam"
      ? `${SERVER_URL}/video_feed_${streamId}`
      : `${SERVER_URL}/stream_${streamId}`;
    return `${basePath}?quality=${qualityHigh ? "high" : "low"}&sharpness=${sharpness}&gamma=${gamma}&deepsort=${useDeepsort}&source=${videoSource}&cacheBuster=${Date.now()}`;
  };

  const handleMouseDown = (index) => setDragIndex(index);
  const handleMouseUp = () => setDragIndex(null);

  const handleMouseMove = (e) => {
    if (dragIndex === null || selectedPolygon === null) return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const updated = [...polygons];
    updated[selectedPolygon].points[dragIndex] = [x, y];
    setPolygons(updated);
  };

  const startDragPolygon = (index, originPoint) => {
    setSelectedPolygon(index);
    setIsDraggingPolygon(true);
    setDragOffset(originPoint);
  };

  const handleCanvasMouseMove = (e) => {
    if (dragIndex !== null) {
      handleMouseMove(e);
      return;
    }

    if (!isDraggingPolygon || selectedPolygon === null) return;

    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const dx = x - dragOffset[0];
    const dy = y - dragOffset[1];

    const updated = [...polygons];
    updated[selectedPolygon].points = updated[selectedPolygon].points.map(
      ([px, py]) => [px + dx, py + dy]
    );
    setPolygons(updated);
    setDragOffset([x, y]);
  };

  const stopDragPolygon = () => {
    setIsDraggingPolygon(false);
    setDragOffset([0, 0]);
  };

  const handleApplyPolygon = async () => {
    await sendPolygons(streamId, polygons);
    setAppliedPolygons(polygons);
    const img = document.getElementById(`video-${streamId}`);
    if (img) img.src = getStreamURL();
  };

  const handleVideoUpload = async (e) => {
    const file = e.target.files[0];
    await uploadVideo(streamId, file);
    setVideoUploaded(true);
    setBackgroundUrl(`${SERVER_URL}/get_screenshot_${streamId}?t=${Date.now()}`);
  };

  const handleResetStream = () => {
    setVideoUploaded(false);
    setVideoSource("video_1.mp4");
  };

  const handleConfidenceChange = async (e) => {
    const val = parseFloat(e.target.value);
    setConfidenceVal(val);
    await setConfidence(streamId, val);
  };

  const handleAddPolygon = () => {
    const color = zoneTypes[zoneType] || "red";
    const newPolygon = {
      label: zoneType,
      color,
      points: generateRegularPolygon(shapePoints),
    };
    const updated = [...polygons, newPolygon];
    setPolygons(updated);
    setSelectedPolygon(updated.length - 1);
  };

  const handleDeletePolygon = async () => {
    if (polygons.length <= 1 || selectedPolygon === null) return;
    const updated = polygons.filter((_, idx) => idx !== selectedPolygon);
    setPolygons(updated);
    setSelectedPolygon(null);
    await sendPolygons(streamId, updated);
  };

  const handleClearAll = async () => {
    setPolygons([]);
    setAppliedPolygons([]);
    setSelectedPolygon(null);
    await sendPolygons(streamId, []);
  };

  const handleSourceChange = async (source) => {
    setVideoSource(source);
    const body = { video_path: source, confidence };
    try {
      await fetch(`${SERVER_URL}/switch_stream_${streamId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setVideoUploaded(true);
    } catch (err) {
      console.error("Failed to switch stream:", err);
    }
  };

  // 🔶 styles that adapt when fullscreen is active
  const videoContainerStyle = isFullscreen
    ? {
        width: "100vw",
        height: "100vh",
        background: "#000",
        margin: 0,
        padding: 0,
      }
    : {};

  const liveImageStyle = isFullscreen
    ? { width: "100%", height: "100%", objectFit: "contain", cursor: "zoom-out" }
    : { cursor: "zoom-in" };

  return (
    <div className="stream-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3><span role="img" aria-label="camera">📷</span> Camera {streamId}</h3>
          <p>Active Zones: {appliedPolygons.length}</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            value={videoSource}
            onChange={(e) => handleSourceChange(e.target.value)}
            style={{ padding: "6px", fontSize: "14px", borderRadius: "4px", border: "1px solid #ccc" }}
          >
            <option value="video_1.mp4">📁 Uploaded Video</option>
            <option value="webcam">📷 Webcam</option>
          </select>

          {/* 🔶 Fullscreen toggle button */}
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit full screen" : "Full screen"}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid #ccc",
              background: "#fff",
              cursor: "pointer"
            }}
          >
            {isFullscreen ? "🗗" : "⛶"}
          </button>
        </div>
      </div>

      <div className="canvas-wrapper">
        <svg
          ref={svgRef}
          width={640}
          height={480}
          className="canvas"
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={() => {
            handleMouseUp();
            stopDragPolygon();
          }}
        >
          {backgroundUrl && (
            <image href={backgroundUrl} x="0" y="0" width="640" height="480" preserveAspectRatio="xMidYMid slice" />
          )}
          {polygons.map((poly, pIdx) => {
            const fillColor =
              poly.color === "red" ? "rgba(255, 0, 0, 0.3)" :
              poly.color === "orange" ? "rgba(255, 165, 0, 0.3)" :
              "rgba(0, 255, 0, 0.3)";

            return (
              <g key={pIdx}>
                <polygon
                  points={poly.points.map(([x, y]) => `${x},${y}`).join(" ")}
                  fill={fillColor}
                  stroke={poly.color}
                  strokeWidth={2}
                  onClick={() => setSelectedPolygon(pIdx)}
                />
                <text x={poly.points[0][0]} y={poly.points[0][1] - 10} fill={poly.color} fontSize="14" fontWeight="bold">
                  {poly.label}
                </text>
                {pIdx === selectedPolygon &&
                  poly.points.map(([x, y], i) => (
                    <circle key={i} cx={x} cy={y} r={6} fill="blue" onMouseDown={() => handleMouseDown(i)} />
                  ))}
                {pIdx === selectedPolygon && (
                  <circle
                    cx={poly.points[0][0]}
                    cy={poly.points[0][1]}
                    r={10}
                    fill="rgba(0,0,0,0.3)"
                    stroke="white"
                    strokeWidth={2}
                    cursor="move"
                    onMouseDown={() => startDragPolygon(pIdx, poly.points[0])}
                  />
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="controls">
        <input type="file" onChange={handleVideoUpload} />
        <select value={zoneType} onChange={(e) => setZoneType(e.target.value)}>
          {Object.keys(zoneTypes).map((zone) => (
            <option key={zone} value={zone}>{zone}</option>
          ))}
        </select>
        <select value={shapePoints} onChange={(e) => setShapePoints(parseInt(e.target.value))}>
          {[3, 4, 5, 6, 7].map((n) => (
            <option key={n} value={n}>{n}-point</option>
          ))}
        </select>
        <button onClick={handleAddPolygon}>➕ Add Zone</button>
        <button onClick={handleDeletePolygon}>❌ Delete Selected</button>
        <button onClick={handleClearAll}>🧹 Clear All Zones</button>
        <button onClick={handleApplyPolygon}>Apply Polygon(s)</button>
        <button onClick={handleResetStream}>🛑 Stop & Upload New</button>
      </div>

      {/* 🔶 Video container gets fullscreen */}
      <div
        ref={containerRef}
        className="video-wrapper"
        style={videoContainerStyle}
      >
        {videoUploaded && videoSource !== "webcam" && (
          <img
            id={`video-${streamId}`}
            src={getStreamURL()}
            alt={`Stream ${streamId}`}
            className="video"
            style={liveImageStyle}
            onDoubleClick={toggleFullscreen}
          />
        )}
        {videoUploaded && videoSource === "webcam" && (
          <img
            id={`video-${streamId}`}
            src={`${SERVER_URL}/video_feed_${streamId}`}
            alt={`Webcam ${streamId}`}
            className="video"
            style={liveImageStyle}
            onDoubleClick={toggleFullscreen}
          />
        )}
      </div>

      <div className="quality-toggle">
        <label>Video Quality: {qualityHigh ? "High" : "Low"}</label>
        <input type="checkbox" checked={qualityHigh} onChange={() => setQualityHigh(!qualityHigh)} />
      </div>

      <div className="sliders">
        <label>Sharpness: {sharpness.toFixed(2)}</label>
        <input type="range" min="0.5" max="2.0" step="0.1" value={sharpness} onChange={(e) => setSharpness(parseFloat(e.target.value))} />
        <label>Gamma: {gamma.toFixed(2)}</label>
        <input type="range" min="0.8" max="1.5" step="0.05" value={gamma} onChange={(e) => setGamma(parseFloat(e.target.value))} />
      </div>

      <div className="quality-toggle">
        <label>
          <input type="checkbox" checked={useDeepsort} onChange={(e) => setUseDeepsort(e.target.checked)} />
          Enable DeepSORT Tracking
        </label>
      </div>
    </div>
  );
};

export default StreamCard;
