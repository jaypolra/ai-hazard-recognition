import React, { useRef, useEffect, useState } from "react";

const SERVER_URL = "http://localhost:8001";

const SingleCameraView = ({
  selectedCameraId,
  onBackToGrid,
  onSwitchCamera,
  videoSrc,
  qualityHigh = false,
  sharpness = 1.0,
  gamma = 1.0,
  useDeepsort = false,
  syncTime = null
}) => {
  const imgRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    
    if (imgRef.current) {
      // Build stream URL with parameters
      const quality = qualityHigh ? "high" : "low";
      const streamUrl = `${SERVER_URL}/stream_${selectedCameraId}?quality=${quality}&sharpness=${sharpness}&gamma=${gamma}&deepsort=${useDeepsort}&sync_time=${syncTime}`;
      imgRef.current.src = streamUrl;
    }
  }, [selectedCameraId, qualityHigh, sharpness, gamma, useDeepsort]);

  const handleLoad = () => {
    setIsLoading(false);
  };

  const handleError = () => {
    setError("Stream unavailable");
    setIsLoading(false);
  };

  return (
    <div className="single-camera-view">
      <div className="single-camera-header">
        <h2>📺 Camera {selectedCameraId} - Full View</h2>
        <div className="header-controls">
          <div className="camera-switcher">
            {[1, 2, 3, 4].map((camId) => (
              <button
                key={camId}
                className={`camera-switcher-btn ${camId === selectedCameraId ? "active" : ""}`}
                onClick={() => onSwitchCamera(camId)}
              >
                Cam {camId}
              </button>
            ))}
          </div>
          <button className="back-to-grid-btn" onClick={onBackToGrid}>
            ← Back to Grid
          </button>
        </div>
      </div>

      <div className="single-camera-content">
        {isLoading && (
          <div style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            color: "#64748b",
            textAlign: "center"
          }}>
            {error ? error : "Loading stream..."}
          </div>
        )}
        <img
          ref={imgRef}
          onLoad={handleLoad}
          onError={handleError}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            display: isLoading ? "none" : "block"
          }}
          alt={`Camera ${selectedCameraId}`}
        />
      </div>

      <div style={{
        padding: "1rem",
        backgroundColor: "#f5f7fa",
        color: "#64748b",
        textAlign: "center",
        fontSize: "0.9rem",
        borderTop: "1px solid #e4e8f0"
      }}>
        🔴 Live Stream with Zone Detection
      </div>
    </div>
  );
};

export default SingleCameraView;
