import React, { useState } from "react";
import AppHeader from "./components/AppHeader";
import Sidebar from "./components/Sidebar";
import LiveMonitoringPage from "./components/LiveMonitoringPage";
import PolygonConfigPage from "./components/PolygonConfigPage";
import LogsDashboard from "./components/LogsDashboard";
import "./App.css";

function App() {
  const [currentPage, setCurrentPage] = useState("monitoring");
  const [videoSrc, setVideoSrc] = useState(null);

  const handleVideoUpload = (videosObject) => {
    // videosObject is { 1: url, 2: url, 3: url, 4: url }
    setVideoSrc(videosObject);
  };

  const renderPage = () => {
    switch (currentPage) {
      case "monitoring":
        return <LiveMonitoringPage videoSrc={videoSrc} onVideoUpload={handleVideoUpload} />;
      case "polygon-config":
        return <PolygonConfigPage videoSrc={videoSrc} />;
      case "dashboard":
        return <LogsDashboard />;
default:
        return <LiveMonitoringPage videoSrc={videoSrc} onVideoUpload={handleVideoUpload} />;
    }
  };

  return (
    <div className="App">
      <AppHeader />
      <div className="main-content">
        <Sidebar currentPage={currentPage} setCurrentPage={setCurrentPage} />
        <div className="page-container">
          {renderPage()}
        </div>
      </div>
    </div>
  );
}

export default App;
