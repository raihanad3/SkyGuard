import { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function FlightPanel({ flight, onClose }) {
  const [history, setHistory] = useState([]);
  
  useEffect(() => {
    if (!flight) return;
    const fetchHistory = async () => {
      try {
        const response = await axios.get(`http://localhost:8000/api/flights/${flight.icao24}/history`);
        setHistory(response.data);
      } catch (error) {
        console.error('Error fetching history:', error);
      }
    };
    fetchHistory();
    const interval = setInterval(fetchHistory, 10000);
    return () => clearInterval(interval);
  }, [flight]);

  if (!flight) return null;

  const age = flight.last_contact ? Math.floor(Date.now() / 1000) - flight.last_contact : 0;
  const commsStatus = age < 60 ? 'ACTIVE' : age < 300 ? 'DELAYED' : 'LOST';
  const commsColor = commsStatus === 'ACTIVE' ? '#00ff00' : commsStatus === 'DELAYED' ? '#f59e0b' : '#ef4444';

  return (
    <div style={{
      position: 'absolute',
      right: 0,
      top: 0,
      bottom: 0,
      width: '400px',
      backgroundColor: 'rgba(5, 22, 8, 0.95)',
      borderLeft: '2px solid var(--color-primary)',
      padding: '2rem',
      overflowY: 'auto',
      zIndex: 1000
    }}>
      <div className="flex-between mb-4">
        <h2>FLT: {flight.callsign || 'UNKNOWN'}</h2>
        <button 
          onClick={onClose} 
          style={{ background: 'none', color: 'var(--color-primary)', border: 'none', cursor: 'pointer', fontSize: '1.5rem' }}
        >✕</button>
      </div>

      <div className="card mb-4">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <div className="metric-label">ICAO24</div>
            <div style={{ color: '#fff' }}>{flight.icao24.toUpperCase()}</div>
          </div>
          <div>
            <div className="metric-label">SQUAWK</div>
            <div style={{ color: flight.squawk === '7700' || flight.squawk === '7500' || flight.squawk === '7600' ? '#ef4444' : '#fff' }}>
              {flight.squawk || 'NONE'}
            </div>
          </div>
          <div>
            <div className="metric-label">ROUTE</div>
            <div style={{ color: '#00ff00', fontWeight: 'bold' }}>
              {flight.origin_airport_icao && flight.destination_airport_icao 
                ? `${flight.origin_airport_icao} ➔ ${flight.destination_airport_icao}` 
                : 'UNKNOWN'}
            </div>
          </div>
          <div>
            <div className="metric-label">COMMS STATUS</div>
            <div style={{ color: commsColor, fontWeight: 'bold' }}>{commsStatus} ({age}s)</div>
          </div>
          <div>
            <div className="metric-label">ALERT LVL</div>
            <div style={{ color: flight.alert_level === 'HIGH' ? '#ef4444' : flight.alert_level === 'MEDIUM' ? '#f59e0b' : '#3b82f6' }}>
              {flight.alert_level}
            </div>
          </div>
        </div>
      </div>

      <div className="card mb-4">
        <h3 className="mb-4">TELEMETRY</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <div className="metric-label">ALTITUDE</div>
            <div className="metric-value" style={{ fontSize: '1.5rem' }}>{Math.round(flight.altitude)} <span style={{fontSize: '1rem'}}>ft</span></div>
          </div>
          <div>
            <div className="metric-label">SPEED</div>
            <div className="metric-value" style={{ fontSize: '1.5rem' }}>{Math.round(flight.speed)} <span style={{fontSize: '1rem'}}>kts</span></div>
          </div>
          <div>
            <div className="metric-label">HEADING</div>
            <div className="metric-value" style={{ fontSize: '1.5rem' }}>{Math.round(flight.heading)}°</div>
          </div>
          <div>
            <div className="metric-label">V-SPEED</div>
            <div className="metric-value" style={{ fontSize: '1.5rem', color: (flight.vertical_rate || 0) < -1000 ? '#ef4444' : 'var(--color-primary)' }}>
              {Math.round((flight.vertical_rate || 0) * 196.85)} <span style={{fontSize: '1rem'}}>fpm</span>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="mb-4">ALTITUDE PROFILE</h3>
        <div style={{ height: '200px' }}>
          {history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="inferred_at" hide />
                <YAxis stroke="#00ff00" domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0b1115', borderColor: '#00ff00', color: '#00ff00' }}
                  labelFormatter={() => ''}
                />
                <Line type="monotone" dataKey="altitude" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ textAlign: 'center', marginTop: '4rem' }}>AWAITING DATA...</div>
          )}
        </div>
      </div>

    </div>
  );
}
