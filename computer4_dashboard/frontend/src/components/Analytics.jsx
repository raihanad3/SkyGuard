import { useState, useEffect } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';

const COLORS = {
  HIGH: '#ef4444',
  MEDIUM: '#f59e0b',
  LOW: '#3b82f6',
  NORMAL: '#10b981'
};

export default function Analytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/analytics/stats');
      setStats(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching analytics:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1>📊 SYSTEM ANALYTICS</h1>
        <p>STATISTICAL INSIGHTS ON ASIAN FIR ACTIVITY</p>
      </div>

      {loading || !stats ? (
        <div style={{ textAlign: 'center' }}>COMPILING STATISTICS...</div>
      ) : (
        <>
          <h2 className="mb-4">📈 OVERVIEW</h2>
          <div className="metric-grid">
            <div className="card text-center">
              <div className="metric-label">UNIQUE FLIGHTS</div>
              <div className="metric-value">{stats.overview.total_flights.toLocaleString()}</div>
            </div>
            <div className="card text-center">
              <div className="metric-label">DATA POINTS</div>
              <div className="metric-value">{stats.overview.total_positions.toLocaleString()}</div>
            </div>
            <div className="card text-center">
              <div className="metric-label">INFERENCES</div>
              <div className="metric-value">{stats.overview.total_inferences.toLocaleString()}</div>
            </div>
            <div className="card text-center">
              <div className="metric-label">TOTAL INCIDENTS</div>
              <div className="metric-value">{stats.overview.total_alerts.toLocaleString()}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
            <div className="card">
              <h3 className="mb-4 text-center">🚨 INCIDENT BREAKDOWN</h3>
              <div style={{ height: '300px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={stats.alert_distribution.map(d => ({ name: d.alert_level, value: d.count }))}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {stats.alert_distribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[entry.alert_level] || '#fff'} />
                      ))}
                    </Pie>
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0b1115', borderColor: '#00ff00', color: '#00ff00' }}
                      itemStyle={{ color: '#00ff00' }}
                    />
                    <Legend wrapperStyle={{ color: '#00ff00' }}/>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="card">
              <h3 className="mb-4 text-center">🌍 TARGETS BY REGION</h3>
              <div style={{ height: '300px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.country_distribution} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={true} vertical={false} />
                    <XAxis type="number" stroke="#00ff00" />
                    <YAxis dataKey="country" type="category" stroke="#00ff00" width={100} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0b1115', borderColor: '#00ff00', color: '#00ff00' }}
                      itemStyle={{ color: '#00ff00' }}
                    />
                    <Bar dataKey="count" fill="#8fbc8f" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem', marginTop: '2rem' }}>
             <div className="card">
              <h3 className="mb-4 text-center">📅 INCIDENT TIMELINE (24H)</h3>
              <div style={{ height: '250px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.timeline}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis 
                      dataKey="hour" 
                      stroke="#00ff00" 
                      tickFormatter={(tick) => new Date(tick).getHours() + ":00"} 
                    />
                    <YAxis stroke="#00ff00" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0b1115', borderColor: '#00ff00', color: '#00ff00' }}
                      labelFormatter={(label) => new Date(label).toLocaleString()}
                    />
                    <Legend />
                    <Bar dataKey="count" fill="#f59e0b" name="Alerts" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="card table-container" style={{ marginTop: '2rem' }}>
            <h3 className="mb-4">🏆 TOP REPEAT OFFENDERS</h3>
            <table>
              <thead>
                <tr>
                  <th>ICAO</th>
                  <th>CALLSIGN</th>
                  <th>ALERTS</th>
                  <th>MAX SCORE</th>
                  <th>MAX LVL</th>
                  <th>LAST DETECTED</th>
                </tr>
              </thead>
              <tbody>
                {stats.top_offenders.map((offender) => (
                  <tr key={offender.icao24}>
                    <td>{offender.icao24}</td>
                    <td>{offender.callsign || 'N/A'}</td>
                    <td>{offender.alert_count}</td>
                    <td>{(offender.max_score * 100).toFixed(1)}%</td>
                    <td className={
                      offender.highest_level === 'HIGH' ? 'text-danger' :
                      offender.highest_level === 'MEDIUM' ? 'text-warning' : 'text-info'
                    }>{offender.highest_level}</td>
                    <td>{new Date(offender.last_alert).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
