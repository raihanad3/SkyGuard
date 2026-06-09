/**
 * VESSEL GUARD — Dashboard JavaScript
 * Real-time vessel tracking and anomaly detection visualization.
 */

// ============================================================
// Global State
// ============================================================
const state = {
    map: null,
    markers: {},          // mmsi -> L.marker
    socket: null,
    alerts: [],
    vesselCount: 0,
    connected: false,
};

// ============================================================
// Flag Emoji Mapping
// ============================================================
const FLAG_EMOJI = {
    'CN': '🇨🇳', 'VN': '🇻🇳', 'PH': '🇵🇭', 'TH': '🇹🇭',
    'MY': '🇲🇾', 'TW': '🇹🇼', 'KR': '🇰🇷', 'ID': '🇮🇩',
    'JP': '🇯🇵', 'SG': '🇸🇬', 'US': '🇺🇸', 'PA': '🇵🇦',
    'LR': '🇱🇷', 'MH': '🇲🇭', 'HK': '🇭🇰', 'UNKNOWN': '🏴',
};

// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initSocket();
    initClock();
    loadInitialData();
});

// ============================================================
// Map Initialization
// ============================================================
function initMap() {
    // Center on Indonesia
    state.map = L.map('map', {
        center: [-2.5, 118.0],
        zoom: 5,
        zoomControl: true,
        attributionControl: true
    });

    // Dark-themed tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(state.map);

    // Draw Indonesia EEZ bounding box
    const eezBounds = [
        [-14.0, 92.0],
        [-14.0, 141.5],
        [8.0, 141.5],
        [8.0, 92.0]
    ];

    L.polygon(eezBounds, {
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.05,
        weight: 2,
        dashArray: '8, 4',
        interactive: false
    }).addTo(state.map).bindTooltip('Indonesia EEZ', {
        permanent: false,
        direction: 'center',
        className: 'eez-tooltip'
    });

    // Draw critical zones
    const criticalZones = {
        'Laut Natuna Utara': [[1.0, 105.0], [7.0, 112.0]],
        'Selat Malaka': [[0.5, 98.0], [4.0, 104.0]],
        'Laut Arafura': [[-10.0, 131.0], [-4.0, 141.0]],
        'Laut Sulawesi': [[-1.0, 117.0], [5.0, 127.0]],
        'Laut Jawa': [[-8.0, 106.0], [-4.0, 117.0]]
    };

    for (const [name, bounds] of Object.entries(criticalZones)) {
        const rect = L.rectangle(bounds, {
            color: '#f59e0b',
            fillColor: '#f59e0b',
            fillOpacity: 0.03,
            weight: 1,
            dashArray: '4, 4',
            interactive: false
        }).addTo(state.map);

        rect.bindTooltip(name, {
            permanent: false,
            direction: 'center',
            className: 'zone-tooltip'
        });
    }
}

// ============================================================
// Socket.IO Initialization
// ============================================================
function initSocket() {
    state.socket = io();

    state.socket.on('connect', () => {
        state.connected = true;
        updateConnectionStatus('connected', 'Live — Streaming');
        console.log('✅ Connected to dashboard server');
    });

    state.socket.on('disconnect', () => {
        state.connected = false;
        updateConnectionStatus('error', 'Disconnected');
        console.log('❌ Disconnected from server');
    });

    // Real-time vessel updates
    state.socket.on('vessel_update', (data) => {
        updateVesselMarker(data);
    });

    // Real-time alerts
    state.socket.on('new_alert', (data) => {
        addAlertToFeed(data);
        highlightVessel(data.mmsi, data.alert_level);
    });

    // Stats updates
    state.socket.on('stats_update', (data) => {
        updateStats(data);
    });

    // Vessels update
    state.socket.on('vessels_update', (data) => {
        data.forEach(v => updateVesselMarker(v));
    });
}

// ============================================================
// Clock
// ============================================================
function initClock() {
    function updateClock() {
        const now = new Date();
        const wib = new Date(now.getTime() + (7 * 60 * 60 * 1000));
        const h = String(wib.getUTCHours()).padStart(2, '0');
        const m = String(wib.getUTCMinutes()).padStart(2, '0');
        const s = String(wib.getUTCSeconds()).padStart(2, '0');
        document.getElementById('live-clock').textContent = `${h}:${m}:${s} WIB`;
    }
    updateClock();
    setInterval(updateClock, 1000);
}

// ============================================================
// Data Loading
// ============================================================
function loadInitialData() {
    // Load stats
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => updateStats(data))
        .catch(e => console.error('Stats load error:', e));

    // Load active vessels
    fetch('/api/vessels')
        .then(r => r.json())
        .then(data => {
            data.forEach(v => updateVesselMarker(v));
        })
        .catch(e => console.error('Vessels load error:', e));

    // Load recent alerts
    fetch('/api/alerts')
        .then(r => r.json())
        .then(data => {
            // Reverse to show oldest first (newest will be at top)
            data.reverse().forEach(a => {
                a.reasons = typeof a.reasons === 'string' ? JSON.parse(a.reasons) : a.reasons;
                addAlertToFeed(a, false);
            });
        })
        .catch(e => console.error('Alerts load error:', e));

    // Periodic refresh
    setInterval(() => {
        if (state.socket && state.connected) {
            state.socket.emit('request_stats');
        }
    }, 10000);
}

// ============================================================
// Map Markers
// ============================================================
function updateVesselMarker(data) {
    const mmsi = data.mmsi;
    const lat = data.latitude;
    const lon = data.longitude;
    const alertLevel = data.alert_level || 'NORMAL';

    if (!lat || !lon) return;

    // Determine marker color
    const color = getAlertColor(alertLevel);
    const iconSize = alertLevel === 'HIGH' ? 14 : alertLevel === 'MEDIUM' ? 12 : 10;

    // Create custom icon
    const icon = L.divIcon({
        className: 'vessel-marker',
        html: `<div style="
            width: ${iconSize}px;
            height: ${iconSize}px;
            background: ${color};
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.8);
            box-shadow: 0 0 ${alertLevel === 'HIGH' ? '12' : '6'}px ${color};
            ${alertLevel === 'HIGH' ? 'animation: pulse 1.5s infinite;' : ''}
        "></div>`,
        iconSize: [iconSize + 4, iconSize + 4],
        iconAnchor: [(iconSize + 4) / 2, (iconSize + 4) / 2]
    });

    // Build popup content
    const flag = FLAG_EMOJI[data.flag_country] || '🏳️';
    const shipName = data.ship_name || 'Unknown Vessel';
    const shipType = data.ship_type || data.ship_type_name || 'Unknown';
    const speed = data.speed != null ? `${Number(data.speed).toFixed(1)} kn` : 'N/A';
    const score = data.anomaly_score != null ?
        `${(Number(data.anomaly_score) * 100).toFixed(0)}%` : 'N/A';

    const popupContent = `
        <div class="vessel-popup-title">${flag} ${shipName}</div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">MMSI</span>
            <span class="vessel-popup-value">${mmsi}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Flag</span>
            <span class="vessel-popup-value">${data.flag_country || 'Unknown'}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Type</span>
            <span class="vessel-popup-value">${shipType}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Speed</span>
            <span class="vessel-popup-value">${speed}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Position</span>
            <span class="vessel-popup-value">${Number(lat).toFixed(4)}, ${Number(lon).toFixed(4)}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Risk Score</span>
            <span class="vessel-popup-value" style="color: ${color}">${score}</span>
        </div>
        <div class="vessel-popup-row">
            <span class="vessel-popup-label">Alert</span>
            <span class="vessel-popup-value" style="color: ${color}">${alertLevel}</span>
        </div>
    `;

    if (state.markers[mmsi]) {
        // Update existing marker
        state.markers[mmsi].setLatLng([lat, lon]);
        state.markers[mmsi].setIcon(icon);
        state.markers[mmsi].setPopupContent(popupContent);
    } else {
        // Create new marker
        const marker = L.marker([lat, lon], { icon })
            .addTo(state.map)
            .bindPopup(popupContent, { maxWidth: 280 });

        state.markers[mmsi] = marker;
    }
}

function highlightVessel(mmsi, alertLevel) {
    const marker = state.markers[mmsi];
    if (marker) {
        // Flash effect on marker
        const el = marker.getElement();
        if (el) {
            el.style.transition = 'transform 0.3s';
            el.style.transform = 'scale(2)';
            setTimeout(() => {
                el.style.transform = 'scale(1)';
            }, 500);
        }
    }
}

// ============================================================
// Alert Feed
// ============================================================
function addAlertToFeed(data, isNew = true) {
    const alertList = document.getElementById('alert-list');

    // Remove placeholder if present
    const placeholder = alertList.querySelector('.alert-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const level = (data.alert_level || 'LOW').toLowerCase();
    const flag = FLAG_EMOJI[data.flag_country] || '🏳️';
    const shipName = data.ship_name || 'Unknown Vessel';
    const time = data.timestamp || data.created_at || new Date().toLocaleTimeString();
    const score = data.anomaly_score != null ?
        (Number(data.anomaly_score) * 100).toFixed(0) : 'N/A';
    const reasons = data.reasons || [];
    const reasonsList = Array.isArray(reasons) ? reasons : [];

    const alertEl = document.createElement('div');
    alertEl.className = `alert-item ${level}${isNew ? ' new' : ''}`;
    alertEl.onclick = () => {
        if (data.latitude && data.longitude) {
            state.map.flyTo([data.latitude, data.longitude], 10, {
                duration: 1.5
            });
            if (state.markers[data.mmsi]) {
                state.markers[data.mmsi].openPopup();
            }
        }
    };

    const displayTime = typeof time === 'string' && time.includes(' ')
        ? time.split(' ').pop()
        : time;

    alertEl.innerHTML = `
        <div class="alert-header">
            <span class="alert-level ${level}">${data.alert_level || 'LOW'}</span>
            <span class="alert-score" style="color: ${getAlertColor(data.alert_level)}">${score}%</span>
            <span class="alert-time">${displayTime}</span>
        </div>
        <div class="alert-vessel">${flag} ${shipName}</div>
        <div class="alert-detail">
            MMSI: ${data.mmsi || 'N/A'} · ${data.flag_country || '??'}
            ${data.zone_name ? ` · ${data.zone_name}` : ''}
        </div>
        ${reasonsList.length > 0 ? `
            <div class="alert-reason">
                ${reasonsList.slice(0, 3).map(r => `• ${r}`).join('<br>')}
            </div>
        ` : ''}
    `;

    // Insert at top
    alertList.insertBefore(alertEl, alertList.firstChild);

    // Keep max 100 alerts in DOM
    while (alertList.children.length > 100) {
        alertList.removeChild(alertList.lastChild);
    }

    // Update alert counts
    if (isNew) {
        updateAlertCounts(data.alert_level);
    }
}

function clearAlerts() {
    const alertList = document.getElementById('alert-list');
    alertList.innerHTML = `
        <div class="alert-placeholder">
            <span class="placeholder-icon">📡</span>
            <p>Alerts cleared</p>
            <p class="placeholder-sub">New alerts will appear here</p>
        </div>
    `;
}

// ============================================================
// Stats Updates
// ============================================================
function updateStats(data) {
    if (data.total_vessels != null) {
        animateNumber('total-vessels', data.total_vessels);
    }
    if (data.total_positions != null) {
        animateNumber('total-positions', data.total_positions);
    }
    if (data.alerts_by_level) {
        animateNumber('alert-high-count', data.alerts_by_level.HIGH || 0);
        animateNumber('alert-medium-count', data.alerts_by_level.MEDIUM || 0);
        animateNumber('alert-low-count', data.alerts_by_level.LOW || 0);
    }
}

function updateAlertCounts(level) {
    if (level === 'HIGH') {
        incrementNumber('alert-high-count');
    } else if (level === 'MEDIUM') {
        incrementNumber('alert-medium-count');
    } else if (level === 'LOW') {
        incrementNumber('alert-low-count');
    }
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const diff = target - current;
    const steps = Math.min(Math.abs(diff), 20);
    const stepValue = diff / steps;
    let step = 0;

    const interval = setInterval(() => {
        step++;
        if (step >= steps) {
            el.textContent = formatNumber(target);
            clearInterval(interval);
        } else {
            el.textContent = formatNumber(
                Math.round(current + stepValue * step));
        }
    }, 30);
}

function incrementNumber(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const current = parseInt(el.textContent.replace(/,/g, '')) || 0;
    el.textContent = formatNumber(current + 1);
}

function formatNumber(num) {
    return num.toLocaleString('id-ID');
}

// ============================================================
// UI Helpers
// ============================================================
function updateConnectionStatus(status, text) {
    const dot = document.querySelector('.status-dot');
    const textEl = document.querySelector('.status-text');

    dot.className = `status-dot ${status}`;
    textEl.textContent = text;
}

function getAlertColor(level) {
    switch ((level || '').toUpperCase()) {
        case 'HIGH': return '#ef4444';
        case 'MEDIUM': return '#f59e0b';
        case 'LOW': return '#06b6d4';
        default: return '#10b981';
    }
}

function closeVesselDetail() {
    document.getElementById('vessel-detail').style.display = 'none';
}
