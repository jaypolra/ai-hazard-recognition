import React, { useState, useEffect } from "react";
import PolygonEditor from "./PolygonEditor";

const SERVER_URL = "http://localhost:8001";

const PolygonConfigPage = ({ videoSrc }) => {
  const [selectedCamera, setSelectedCamera] = useState(1);
  const [zoneStatus, setZoneStatus] = useState({ 1: false, 2: false, 3: false, 4: false });

  useEffect(() => {
    // Load zone status on component mount
    loadZoneStatus();
  }, []);

  const loadZoneStatus = async () => {
    try {
      const response = await fetch(`${SERVER_URL}/check_zones`);
      const data = await response.json();
      setZoneStatus(data);
    } catch (error) {
      console.error("Error loading zone status:", error);
    }
  };

  if (!videoSrc) {
    return (
      <div className="polygon-config-page">
        <div className="polygon-config-header">
          <h2>🔧 Zone Configuration</h2>
          <p>Create and manage detection zones for each camera</p>
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }}>
          <div style={{ textAlign: "center", color: "#64748b" }}>
            <p style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>📹 No video source detected</p>
            <p>Upload videos from the Live Monitoring page first to configure zones.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="polygon-config-page">
      <div className="polygon-config-header">
        <h2>🔧 Zone Configuration</h2>
        <p>Create and manage detection zones for each camera monitoring</p>
      </div>

      <div className="polygon-config-body">
        {/* Camera Selector */}
        <div className="polygon-camera-selector">
          <h3>Select Camera</h3>
          {[1, 2, 3, 4].map((camId) => (
            <div
              key={camId}
              className={`camera-option ${camId === selectedCamera ? "selected" : ""}`}
              onClick={() => setSelectedCamera(camId)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
            >
              <span>Camera {camId}</span>
              {zoneStatus[camId] && (
                <span style={{
                  display: "inline-block",
                  backgroundColor: "#22c55e",
                  color: "white",
                  fontSize: "0.75rem",
                  fontWeight: "600",
                  padding: "0.25rem 0.5rem",
                  borderRadius: "4px",
                  marginLeft: "0.5rem"
                }}>
                  ✓ Zones Configured
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Polygon Editor */}
        <PolygonEditor 
          cameraId={selectedCamera}
          videoSrc={videoSrc[selectedCamera]}
          onZonesApplied={loadZoneStatus}
        />
      </div>
    </div>
  );
};

export default PolygonConfigPage;
