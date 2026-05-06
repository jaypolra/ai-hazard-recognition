import React, { useState, useRef } from "react";
import axios from "axios";

const defaultPoints = [
  [150, 100], [450, 100], [500, 300], [200, 400], [100, 250]
];

const MjpegDashboard = () => {
  const [videoURL, setVideoURL] = useState(null);
  const [videoActive, setVideoActive] = useState(false);
  const [polygon, setPolygon] = useState(defaultPoints);
  const [confidence, setConfidence] = useState(0.3);
  const [dragIndex, setDragIndex] = useState(null);
  const svgRef = useRef(null);
  const debounceTimeout = useRef(null);

  const uploadVideo = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    await axios.post("http://localhost:8001/upload", formData);
    setVideoURL("http://localhost:8001/video_feed?t=" + Date.now());
    setVideoActive(true);
  };

  const resetSession = () => {
    setVideoURL(null);
    setVideoActive(false);
    setPolygon(defaultPoints);
    axios.post("http://localhost:8001/set_polygon", { points: defaultPoints });
  };

  const sendPolygon = (points) => {
    clearTimeout(debounceTimeout.current);
    debounceTimeout.current = setTimeout(() => {
      axios.post("http://localhost:8001/set_polygon", { points }).catch(console.error);
    }, 100);
  };

  const sendConfidence = (value) => {
    axios.post("http://localhost:8001/set_confidence", { confidence: value });
  };

  const handleMouseDown = (index) => setDragIndex(index);

  const handleMouseMove = (e) => {
    if (dragIndex === null) return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const updated = [...polygon];
    updated[dragIndex] = [x, y];
    setPolygon(updated);
    sendPolygon(updated);
  };

  const handleMouseUp = () => setDragIndex(null);

  return (
    <div style={{ display: "flex", gap: "40px", padding: "20px" }}>
      <div style={{ width: 640 }}>
        <h3>🚧 Drag No-Go Zone</h3>
        <svg
          ref={svgRef}
          width="640"
          height="480"
          style={{ border: "1px solid #ccc", cursor: "pointer" }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          <polygon
            points={polygon.map(([x, y]) => `${x},${y}`).join(" ")}
            fill="rgba(255,0,0,0.3)"
            stroke="red"
            strokeWidth="2"
          />
          {polygon.map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="6"
              fill="blue"
              onMouseDown={() => handleMouseDown(i)}
            />
          ))}
        </svg>

        <div style={{ marginTop: 20 }}>
          <label>Confidence Threshold: {confidence.toFixed(2)}</label>
          <input
            type="range"
            min="0.1"
            max="1.0"
            step="0.05"
            value={confidence}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              setConfidence(val);
              sendConfidence(val);
            }}
          />
        </div>
      </div>

      <div>
        
        
        
        {videoURL && (
          <>
            <h4 style={{ marginTop: 20 }}>📺 Output</h4>
            <img src={videoURL} width={640} height={480} alt="Stream" />
          </>
        )}
        <h3>📤 Upload Video + Stream Detection</h3>
        {!videoActive ? (
          <input type="file" onChange={uploadVideo} />
        ) : (
          <button onClick={resetSession}>🛑 Stop & Upload New Video</button>
        )}
      </div>
    </div>
  );
};

export default MjpegDashboard;
