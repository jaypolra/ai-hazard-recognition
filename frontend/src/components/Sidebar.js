import React from "react";

const Sidebar = ({ currentPage, setCurrentPage }) => {
  const menuItems = [
    { id: "monitoring",    label: "Live Monitoring",    icon: "📺" },
    { id: "polygon-config",label: "Zone Configuration", icon: "🔧" },
    { id: "dashboard",     label: "Dashboard & Logs",   icon: "📊" },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-section-title">Navigation</div>
        {menuItems.map((item) => (
          <div
            key={item.id}
            className={`sidebar-item ${currentPage === item.id ? "active" : ""}`}
            onClick={() => setCurrentPage(item.id)}
            title={item.label}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">System</div>
        <div style={{ padding: "0.75rem 1rem", color: "#64748b", fontSize: "0.85rem" }}>
          <div style={{ marginBottom: "0.35rem" }}>📷 4 Cameras</div>
          <div>🟢 All Online</div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
