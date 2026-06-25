import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Tooltip as LeafletTooltip, GeoJSON } from 'react-leaflet';
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

import FlightPanel from './FlightPanel';

export default function MapView() {
  const [flights, setFlights] = useState([]);
  const [trails, setTrails] = useState({});
  const [weather, setWeather] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedFlight, setSelectedFlight] = useState(null);

  const fetchFlights = async () => {
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL}/api/flights/live`);
      const newFlights = response.data;
      setFlights(newFlights);
      
      // Update trails
      setTrails(prev => {
        const next = { ...prev };
        newFlights.forEach(f => {
          if (!next[f.icao24]) next[f.icao24] = [];
          // Add new point, keep last 20 points
          next[f.icao24] = [...next[f.icao24], [f.latitude, f.longitude]].slice(-20);
        });
        return next;
      });

      // Update selected flight data if it's currently selected
      setSelectedFlight(prev => {
        if (!prev) return null;
        const updated = newFlights.find(f => f.icao24 === prev.icao24);
        return updated || prev;
      });

      setLoading(false);
    } catch (error) {
      console.error('Error fetching flights:', error);
      setLoading(false);
    }
  };

  const fetchWeather = async () => {
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL}/api/weather/live`);
      setWeather(response.data);
    } catch (error) {
      console.error('Error fetching weather:', error);
    }
  };

  useEffect(() => {
    fetchFlights();
    fetchWeather();
    const interval = setInterval(fetchFlights, 10000);
    const weatherInterval = setInterval(fetchWeather, 60000); // 1 min
    return () => {
      clearInterval(interval);
      clearInterval(weatherInterval);
    };
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
          <MapContainer center={[5.0, 110.0]} zoom={4} scrollWheelZoom={true} style={{ cursor: 'crosshair' }}>
            <TileLayer
              attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            
            {/* Weather Overlay */}
            {weather.map((w, idx) => (
              <GeoJSON 
                key={`weather-${idx}`} 
                data={w.geometry} 
                style={() => ({ 
                  color: w.hazard === 'TS' || w.hazard === 'CONVECTIVE' ? '#ef4444' : 
                         w.hazard === 'TURB' ? '#f59e0b' : '#3b82f6',
                  weight: 2,
                  opacity: 0.5,
                  fillOpacity: 0.1 
                })}
              >
                <LeafletTooltip>
                  {w.hazard} - {w.severity}
                </LeafletTooltip>
              </GeoJSON>
            ))}

            {/* Flight Trails */}
            {Object.entries(trails).map(([icao, coords]) => {
              if (coords.length < 2) return null;
              const flight = flights.find(f => f.icao24 === icao);
              const color = flight ? getAlertColor(flight.alert_level) : '#333';
              return (
                <Polyline 
                  key={`trail-${icao}`} 
                  positions={coords} 
                  color={color} 
                  weight={2} 
                  opacity={0.4} 
                  dashArray="4"
                />
              );
            })}

            {/* Flight Markers */}
            {flights.map((flight) => (
              <Marker 
                key={`${flight.icao24}-v2`} 
                position={[flight.latitude, flight.longitude]}
                icon={createCustomIcon(flight.alert_level)}
                eventHandlers={{
                  click: () => setSelectedFlight(flight),
                }}
              >
                <LeafletTooltip direction="right" offset={[10, 0]} opacity={1} permanent={false}>
                  <div style={{ fontFamily: 'monospace', fontWeight: 'bold', fontSize: '0.8rem' }}>
                    {flight.callsign || flight.icao24}<br/>
                    {flight.registration ? `REG: ${flight.registration}` : 'REG: N/A'} | {flight.aircraft_type || 'TYPE N/A'}<br/>
                    {flight.origin_airport_icao && flight.destination_airport_icao && flight.origin_airport_icao !== 'UNKNOWN' ? `${flight.origin_airport_icao} ➔ ${flight.destination_airport_icao}` : 'ROUTE UNKNOWN'}<br/>
                    {Math.round(flight.altitude/100)} FL | {Math.round(flight.speed)} KTS
                  </div>
                </LeafletTooltip>
              </Marker>
            ))}
          </MapContainer>
          
          <FlightPanel flight={selectedFlight} onClose={() => setSelectedFlight(null)} />
        </div>
      )}
    </div>
  );
}
