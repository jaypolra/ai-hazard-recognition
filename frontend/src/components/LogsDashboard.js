import React, { useEffect, useState } from "react";

const SERVER_URL = "http://localhost:8001";

const LogsDashboard = () => {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetch(`${SERVER_URL}/logs`)
      .then((res) => res.json())
      .then((data) => setLogs(data.reverse()));
  }, []);

  return (
    <div className="log-dashboard">
      <h2>📄 Event Log Dashboard</h2>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Camera</th>
            <th>Event</th>
            <th>Confidence</th>
            <th>Polygon</th>
            <th>Screenshot</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, idx) => (
            <tr key={idx}>
              <td>{log.timestamp}</td>
              <td>{log.camera_id}</td>
              <td style={{ color: log.event_type === "violation" ? "red" : "green" }}>{log.event_type}</td>
              <td>{log.confidence}</td>
              <td>{log.polygon_applied ? "Yes" : "No"}</td>
              <td>
                <a href={`${SERVER_URL}/${log.screenshot_path}`} target="_blank" rel="noreferrer">
                  View
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default LogsDashboard;
