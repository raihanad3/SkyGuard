import { useState } from 'react';
import { Radar, Activity, Map as MapIcon, BarChart3 } from 'lucide-react';
import MapView from './components/MapView';
import ThreatLog from './components/ThreatLog';
import Analytics from './components/Analytics';
import { useAlertSound } from './hooks/useAlertSound';

function App() {
  const [activeTab, setActiveTab] = useState('map');
  
  // Enable alert sound notifications
  useAlertSound(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-title">
          <Radar size={32} color="#00ff00" className="pulse" />
          <h2>ATC RADAR</h2>
        </div>
        
        <p className="mb-8" style={{ fontSize: '0.8rem' }}>ASIAN FIR SECTOR CONTROL</p>

        <nav>
          <div 
            className={`nav-link ${activeTab === 'map' ? 'active' : ''}`}
            onClick={() => setActiveTab('map')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <MapIcon size={18} />
              <span>LIVE MAP</span>
            </div>
          </div>
          <div 
            className={`nav-link ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Activity size={18} />
              <span>THREAT LOG</span>
            </div>
          </div>
          <div 
            className={`nav-link ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <BarChart3 size={18} />
              <span>ANALYTICS</span>
            </div>
          </div>
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <div className="card">
            <div className="metric-label">SYSTEM STATUS</div>
            <div className="text-primary mt-4" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#00ff00' }} className="pulse"></div>
              ONLINE
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {activeTab === 'map' && <MapView />}
        {activeTab === 'alerts' && <ThreatLog />}
        {activeTab === 'analytics' && <Analytics />}
      </div>
    </div>
  );
}

export default App;
