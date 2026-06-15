import { useState, useEffect } from 'react';
import axios from 'axios';

export default function ThreatLog() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = async () => {
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL}/api/alerts/recent?limit=50&hours=24`);
      setAlerts(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const getAction = (level) => {
    switch(level) {
      case 'HIGH': return 'INTERCEPT';
      case 'MEDIUM': return 'RADIO CONTACT';
      case 'LOW': return 'MONITOR';
      default: return 'CLEAR';
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1>🚨 THREAT LOG</h1>
        <p>PRIORITY ANOMALY ALERTS (ASIAN FIR)</p>
      </div>

      <div className="card table-container">
        {loading ? (
          <div style={{ textAlign: 'center' }}>LOADING LOGS...</div>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#8fbc8f' }}>NO INCIDENTS DETECTED</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>TIME (UTC)</th>
                <th>CALLSIGN</th>
                <th>REG / TYPE</th>
                <th>ROUTE</th>
                <th>AT AIRPORT</th>
                <th>ICAO</th>
                <th>LVL</th>
                <th>ACTION</th>
                <th>DETAILS</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>{new Date(alert.created_at).toLocaleTimeString()}</td>
                  <td>{alert.callsign || 'N/A'}</td>
                  <td>{alert.registration || 'N/A'} <br/> <small>{alert.aircraft_type || 'N/A'}</small></td>
                  <td style={{ fontFamily: 'monospace' }}>
                    {alert.origin_airport_icao && alert.destination_airport_icao && alert.origin_airport_icao !== 'UNKNOWN'
                      ? `${alert.origin_airport_icao} ➔ ${alert.destination_airport_icao}` 
                      : 'UNKNOWN'}
                  </td>
                  <td style={{ color: alert.near_airport ? '#f59e0b' : '#8fbc8f' }}>
                    {alert.near_airport ? `YES (${alert.airport_code || alert.airport_name})` : 'NO'}
                  </td>
                  <td>{alert.icao24}</td>
                  <td className={
                    alert.alert_level === 'HIGH' ? 'text-danger' :
                    alert.alert_level === 'MEDIUM' ? 'text-warning' : 'text-info'
                  } style={{ fontWeight: 'bold' }}>
                    {alert.alert_level}
                  </td>
                  <td>{getAction(alert.alert_level)}</td>
                  <td style={{ fontSize: '0.85rem' }}>
                    {alert.reasons && typeof alert.reasons === 'object' 
                      ? alert.reasons.join(', ') 
                      : alert.reasons}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
