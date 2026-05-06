import React from "react";
import Sidebar from "./Sidebar";
import LogsDashboard from "./LogsDashboard";
import MonitoringPage from "./MonitoringPage";

const AppLayout = ({ currentView, onChangeView }) => {
  return (
    <div className="flex h-screen">
      <Sidebar onChangeView={onChangeView} />
      <div className="flex-1 p-4 overflow-auto">
        {currentView === "monitor" && <MonitoringPage />}
        {currentView === "dashboard" && <LogsDashboard />}
      </div>
    </div>
  );
};

export default AppLayout;
