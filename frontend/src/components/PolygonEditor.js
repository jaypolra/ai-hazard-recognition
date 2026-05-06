import React, { useState, useRef, useEffect } from "react";
import { setPolygon as sendPolygons, setConfidence } from "../api";

const SERVER_URL = "http://localhost:8001";

// Zone color is determined at runtime by backend hazard logic (RED/GREEN).
// The editor always draws zones in blue — just for placement reference.
const EDITOR_ZONE_COLOR = "#3b82f6";

const PolygonEditor = ({ cameraId, videoSrc, onZonesApplied }) => {
  const [polygons, setPolygons] = useState([]);
  const [selectedPolygon, setSelectedPolygon] = useState(null);
  const [dragIndex, setDragIndex] = useState(null);
  const [isDraggingPolygon, setIsDraggingPolygon] = useState(false);
  const [dragOffset, setDragOffset] = useState([0, 0]);
  const [confidence, setConfidenceVal] = useState(0.5);
  const [polygonList, setPolygonList] = useState([]);
  const [appliedPolygons, setAppliedPolygons] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [frameDimensions, setFrameDimensions] = useState({ width: 0, height: 0 });

  // Backend processes videos at 640x480
  const BACKEND_RESOLUTION = { width: 640, height: 480 };

  const videoRef = useRef(null);
  const svgRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);

  // Load video and saved zones when camera changes
  useEffect(() => {
    if (videoSrc) {
      // Capture first frame from video
      captureFirstFrame();
    }
    
    // Load saved zones for this camera
    loadSavedZones();
  }, [cameraId, videoSrc]);

  const captureFirstFrame = () => {
    const video = document.createElement("video");
    video.src = videoSrc;
    video.onloadedmetadata = () => {
      video.currentTime = 0;
      video.onseeked = () => {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Store ACTUAL video frame dimensions (original, before backend processing)
        setFrameDimensions({ width: video.videoWidth, height: video.videoHeight });
        
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);
        const imgUrl = canvas.toDataURL("image/png");
        if (imgRef.current) {
          imgRef.current.src = imgUrl;
        }
        
        console.log(`[PolygonEditor] Captured frame: ${video.videoWidth}x${video.videoHeight}`);
      };
    };
  };

  const loadSavedZones = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${SERVER_URL}/get_zones_${cameraId}`);
      const data = await response.json();
      
      if (data.zones && data.zones.length > 0) {
        // Ensure zones have both type and label fields
        const zonesWithLabel = data.zones.map(zone => ({
          ...zone,
          label: zone.label || zone.type,
          type: zone.type || zone.label
        }));
        setPolygonList(zonesWithLabel);
        setAppliedPolygons(zonesWithLabel);
        console.log(`[PolygonEditor] Loaded ${zonesWithLabel.length} zones for camera ${cameraId}`);
      } else {
        setPolygonList([]);
        setAppliedPolygons([]);
      }
      setPolygons([]);
      setSelectedPolygon(null);
    } catch (error) {
      console.error("Error loading zones:", error);
      setPolygonList([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMouseDown = (index) => {
    setDragIndex(index);
  };

  const handleMouseUp = () => {
    setDragIndex(null);
  };

  const handleMouseMove = (e) => {
    if (dragIndex !== null && svgRef.current) {
      const svg = svgRef.current;
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const newPolygons = [...polygons];
      if (newPolygons[selectedPolygon]) {
        newPolygons[selectedPolygon][dragIndex] = [x, y];
        setPolygons(newPolygons);
      }
    }
  };

  const addPoint = (e) => {
    if (svgRef.current) {
      const svg = svgRef.current;
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (selectedPolygon === null) {
        setPolygons([...polygons, [[x, y]]]);
        setSelectedPolygon(polygons.length);
      } else {
        const newPolygons = [...polygons];
        newPolygons[selectedPolygon].push([x, y]);
        setPolygons(newPolygons);
      }
    }
  };

  const completePolygon = () => {
    if (selectedPolygon !== null && polygons[selectedPolygon].length >= 3) {
      // Convert display coordinates to frame coordinates first
      const framePoints = getFrameCoordinates(polygons[selectedPolygon]);

      // Then scale to backend's 640x480 resolution
      const backendPoints = scaleToBackendResolution(framePoints);

      // Auto-label zones: "Zone 1", "Zone 2", etc.
      const autoLabel = `Zone ${polygonList.length + 1}`;

      const newPolygonList = [...polygonList, {
        id: polygonList.length,
        label: autoLabel,   // Backend uses this field; color decided by hazard logic
        points: backendPoints,  // Store in backend coordinate system (640x480)
        confidence: confidence
      }];
      setPolygonList(newPolygonList);
      setPolygons(polygons.filter((_, i) => i !== selectedPolygon));
      setSelectedPolygon(null);
    }
  };

  const discardPolygon = () => {
    if (selectedPolygon !== null) {
      setPolygons(polygons.filter((_, i) => i !== selectedPolygon));
      setSelectedPolygon(null);
    }
  };

  const removePolygonFromList = (id) => {
    setPolygonList(polygonList.filter(p => p.id !== id));
  };

  const applyPolygons = async () => {
    try {
      await sendPolygons(cameraId, polygonList);
      setAppliedPolygons(polygonList);
      if (onZonesApplied) {
        onZonesApplied();
      }
      alert("Zones applied to Camera " + cameraId);
    } catch (error) {
      console.error("Error applying zones:", error);
      alert("Failed to apply zones");
    }
  };

  const handleConfidenceChange = (e) => {
    const val = parseFloat(e.target.value);
    setConfidenceVal(val);
    setConfidence(cameraId, val);
  };

  const scaleFromBackendResolution = (points) => {
    if (frameDimensions.width === 0) return points;
    
    // Scale from backend's 640x480 back to original video resolution
    const scaleX = frameDimensions.width / BACKEND_RESOLUTION.width;
    const scaleY = frameDimensions.height / BACKEND_RESOLUTION.height;
    
    return points.map(([x, y]) => [x * scaleX, y * scaleY]);
  };

  const getScaledPoints = (points) => {
    if (frameDimensions.width === 0 || !imgRef.current) return points;
    
    // Points are stored in backend resolution (640x480), convert to original frame
    const originalFramePoints = scaleFromBackendResolution(points);
    
    const imgElement = imgRef.current;
    
    // Use offsetLeft/offsetTop for relative positioning
    const offsetX = imgElement.offsetLeft;
    const offsetY = imgElement.offsetTop;
    const displayedWidth = imgElement.offsetWidth;
    const displayedHeight = imgElement.offsetHeight;
    
    // Calculate scale factors from frame to display
    const scaleX = displayedWidth / frameDimensions.width;
    const scaleY = displayedHeight / frameDimensions.height;
    
    // Scale points from frame to display, then add offset for letterboxing
    return originalFramePoints.map(([x, y]) => [
      x * scaleX + offsetX,
      y * scaleY + offsetY
    ]);
  };

  const getFrameCoordinates = (points) => {
    if (frameDimensions.width === 0 || !imgRef.current) return points;
    
    const imgElement = imgRef.current;
    
    // Use offsetLeft/offsetTop for relative positioning
    const offsetX = imgElement.offsetLeft;
    const offsetY = imgElement.offsetTop;
    const displayedWidth = imgElement.offsetWidth;
    const displayedHeight = imgElement.offsetHeight;
    
    // Calculate scale factors from display to frame
    const scaleX = frameDimensions.width / displayedWidth;
    const scaleY = frameDimensions.height / displayedHeight;
    
    // Convert points: subtract offset, then scale to frame coordinates
    return points.map(([x, y]) => [
      (x - offsetX) * scaleX,
      (y - offsetY) * scaleY
    ]);
  };

  const scaleToBackendResolution = (points) => {
    if (frameDimensions.width === 0) return points;
    
    // Scale from original video resolution to backend's 640x480
    const scaleX = BACKEND_RESOLUTION.width / frameDimensions.width;
    const scaleY = BACKEND_RESOLUTION.height / frameDimensions.height;
    
    return points.map(([x, y]) => [x * scaleX, y * scaleY]);
  };

  if (isLoading) {
    return (
      <div className="polygon-editor-container">
        <div className="polygon-editor-canvas-area" style={{ justifyContent: "center", alignItems: "center" }}>
          <div style={{ color: "#64748b" }}>Loading zones...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="polygon-editor-container">
      <div className="polygon-editor-canvas-area" ref={containerRef} onClick={addPoint}>
        <img
          ref={imgRef}
          style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", display: "block" }}
          alt="First frame"
        />
        <svg
          ref={svgRef}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            cursor: "crosshair"
          }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Existing completed polygons — always drawn in blue (editor reference only).
              Zone color at runtime is determined by backend hazard logic (RED/GREEN). */}
          {polygonList.map((poly, idx) => {
            const scaledPoints = getScaledPoints(poly.points);
            return (
              <g key={`completed-${idx}`}>
                <polygon
                  points={scaledPoints.map(p => p.join(",")).join(" ")}
                  fill={EDITOR_ZONE_COLOR}
                  fillOpacity="0.1"
                  stroke={EDITOR_ZONE_COLOR}
                  strokeWidth="2"
                />
                {scaledPoints.map((point, pointIdx) => (
                  <circle
                    key={`completed-point-${idx}-${pointIdx}`}
                    cx={point[0]}
                    cy={point[1]}
                    r="5"
                    fill={EDITOR_ZONE_COLOR}
                  />
                ))}
                {/* Zone label */}
                {scaledPoints.length > 0 && (
                  <text
                    x={scaledPoints[0][0] + 6}
                    y={scaledPoints[0][1] - 6}
                    fill={EDITOR_ZONE_COLOR}
                    fontSize="13"
                    fontWeight="600"
                    style={{ pointerEvents: "none", userSelect: "none" }}
                  >
                    {poly.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Polygon being drawn */}
          {selectedPolygon !== null && polygons[selectedPolygon] && (
            <g>
              {polygons[selectedPolygon].length > 1 && (
                <polyline
                  points={polygons[selectedPolygon].map(p => p.join(",")).join(" ")}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="2"
                />
              )}
              {polygons[selectedPolygon].map((point, idx) => (
                <circle
                  key={idx}
                  cx={point[0]}
                  cy={point[1]}
                  r="6"
                  fill="#3b82f6"
                  stroke="#ffffff"
                  strokeWidth="2"
                  onMouseDown={() => handleMouseDown(idx)}
                  style={{ cursor: "move" }}
                />
              ))}
            </g>
          )}
        </svg>
      </div>

      <div className="polygon-tools">
        <span style={{ fontSize: "0.85rem", color: "#64748b", fontWeight: "500" }}>
          Click on the image to place zone vertices. Zone color is set automatically by hazard logic.
        </span>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <label style={{ fontSize: "0.85rem", color: "#64748b", fontWeight: "500" }}>
            Confidence: {confidence.toFixed(2)}
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={confidence}
            onChange={handleConfidenceChange}
            style={{ width: "150px" }}
          />
        </div>

        {selectedPolygon !== null && polygons[selectedPolygon] && polygons[selectedPolygon].length >= 3 && (
          <>
            <button className="polygon-tool-btn success" onClick={completePolygon}>
              ✓ Complete Zone
            </button>
            <button className="polygon-tool-btn danger" onClick={discardPolygon}>
              ✕ Discard
            </button>
          </>
        )}

        {polygonList.length > 0 && (
          <button className="polygon-tool-btn success" onClick={applyPolygons} style={{ marginLeft: "auto" }}>
            ✓ Apply All Zones
          </button>
        )}
      </div>

      {polygonList.length > 0 && (
        <div className="polygon-list">
          <h3>Zones ({polygonList.length})</h3>
          {polygonList.map((poly, idx) => (
            <div
              key={idx}
              className="polygon-item"
              style={{ borderLeft: `4px solid ${EDITOR_ZONE_COLOR}` }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: "600", color: EDITOR_ZONE_COLOR }}>
                  {poly.label}
                </span>
                <button
                  onClick={() => removePolygonFromList(poly.id)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#ef4444",
                    cursor: "pointer",
                    fontSize: "0.9rem",
                    fontWeight: "bold"
                  }}
                  title="Remove"
                >
                  ×
                </button>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem" }}>
                {poly.points.length} points • conf {(poly.confidence * 100).toFixed(0)}% • color set by backend
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PolygonEditor;
