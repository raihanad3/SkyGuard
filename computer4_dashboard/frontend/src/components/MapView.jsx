import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import axios from 'axios';

// Fix Leaflet default icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const getAlertColor = (level) => {
  switch (level) {
    case 'HIGH': return '#ff0000';
    case 'MEDIUM': return '#f59e0b';
    case 'LOW': return '#3b82f6';
    default: return '#00ff00';
  }
};

const createCustomIcon = (level) => {
  const color = getAlertColor(level);
  return L.divIcon({
    className: 'custom-icon',
    html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; box-shadow: 0 0 8px ${color};"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  });
};

export default function MapView() {
  const [flights, setFlights] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchFlights = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/flights/live');
      setFlights(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching flights:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFlights();
    const interval = setInterval(fetchFlights, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1>📡 RADAR: ASIAN FIR</h1>
        <p>LIVE SURVEILLANCE & THREAT DETECTION</p>
      </div>

      <div className="metric-grid">
        <div className="card">
          <div className="metric-label">CONTACTS</div>
          <div className="metric-value">{flights.length}</div>
        </div>
        <div className="card">
          <div className="metric-label" style={{ color: '#ff0000' }}>LVL 1 THREAT</div>
          <div className="metric-value" style={{ color: '#ff0000' }}>
            {flights.filter(f => f.alert_level === 'HIGH').length}
          </div>
        </div>
        <div className="card">
          <div className="metric-label" style={{ color: '#f59e0b' }}>LVL 2 WARN</div>
          <div className="metric-value" style={{ color: '#f59e0b' }}>
            {flights.filter(f => f.alert_level === 'MEDIUM').length}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>INITIALIZING RADAR...</div>
      ) : (
        <div style={{ position: 'relative', zIndex: 1 }}>
          <MapContainer center={[5.0, 110.0]} zoom={4} scrollWheelZoom={true}>
            <TileLayer
              attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            {flights.map((flight) => (
              <Marker 
                key={flight.icao24} 
                position={[flight.latitude, flight.longitude]}
                icon={createCustomIcon(flight.alert_level)}
              >
                <Popup>
                  <div>
                    <h3 style={{ color: '#000', borderBottom: '1px solid #333', paddingBottom: '4px', marginBottom: '8px' }}>
                      FLT: {flight.callsign || 'N/A'} ({flight.icao24})
                    </h3>
                    <div><strong>ORG:</strong> {flight.origin_country}</div>
                    <div><strong>ALT:</strong> {Math.round(flight.altitude)} FL</div>
                    <div><strong>SPD:</strong> {Math.round(flight.speed)} KTS</div>
                    <div><strong>HDG:</strong> {Math.round(flight.heading)}°</div>
                    <hr style={{ margin: '8px 0', borderColor: '#ccc' }} />
                    <div><strong>STATUS:</strong> <span style={{ color: getAlertColor(flight.alert_level), fontWeight: 'bold' }}>{flight.alert_level}</span></div>
                    <div><strong>SCORE:</strong> {(flight.anomaly_score * 100).toFixed(1)}%</div>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      )}
    </div>
  );
}
