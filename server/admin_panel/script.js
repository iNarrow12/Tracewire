/**
 * TraceWire Admin Controller
 * Updated to use X-Password header (matching server.py)
 */

let AUTH_TOKEN = localStorage.getItem('tracewire_token') || '';
let map = null;
let currentMarker = null;
let selectedAgentId = null;
let agents = [];
let pollingIntervals = [];

// --- UI ELEMENTS ---
const agentListEl = document.getElementById('agent-list');
const dashboardEl = document.getElementById('dashboard');
const noSelectionEl = document.getElementById('no-selection');
const authModal = document.getElementById('auth-modal');
const authTokenInp = document.getElementById('auth-token');
const btnLogin = document.getElementById('btn-login');

// --- INITIALIZATION ---
function init() {
    lucide.createIcons();
    if (!AUTH_TOKEN) {
        authModal.classList.remove('hidden');
    } else {
        authModal.classList.add('hidden');
        startPolling();
    }
}

// --- AUTH ---
btnLogin.addEventListener('click', () => {
    const token = authTokenInp.value.trim();
    if (token) {
        AUTH_TOKEN = token;
        localStorage.setItem('tracewire_token', token);
        authModal.classList.add('hidden');
        startPolling();
    }
});

document.getElementById('btn-settings').addEventListener('click', () => {
    authModal.classList.remove('hidden');
});

// --- API CORE ---   <--- THIS IS THE MAIN CHANGE
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'X-Password': AUTH_TOKEN,        // ← Changed from X-Auth-Token to X-Password
            'Content-Type': 'application/json'
        }
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const res = await fetch(endpoint, options);

        if (res.status === 401) {
            console.warn("401 Unauthorized - Showing auth modal");
            authModal.classList.remove('hidden');
            throw new Error('Unauthorized');
        }

        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(errBody.detail || `HTTP Error ${res.status}`);
        }

        return await res.json();
    } catch (err) {
        console.error(`[API ERROR] ${endpoint}:`, err.message);
        return null;
    }
}

// --- POLLING ENGINE ---
function startPolling() {
    pollingIntervals.forEach(clearInterval);
    pollingIntervals = [];

    fetchAgents();
    pollingIntervals.push(setInterval(fetchAgents, 5000));
    pollingIntervals.push(setInterval(() => {
        if (selectedAgentId) fetchAgentData(selectedAgentId);
    }, 3000));
}

async function fetchAgents() {
    const data = await apiCall('/agents');
    if (data) {
        agents = data;
        renderAgentList();
    }
}

async function fetchAgentData(id) {
    const data = await apiCall(`/agents/${id}/list`);
    if (data) {
        updateDashboard(data);
    }
}

// --- UI RENDERING ---
function renderAgentList() {
    const search = document.getElementById('agent-search').value.toLowerCase();
    const filtered = agents.filter(a =>
        (a.agent_name || '').toLowerCase().includes(search) ||
        (a.agent_id || '').toLowerCase().includes(search)
    );

    const newHTML = filtered.map(agent => `
        <div class="agent-card ${selectedAgentId === agent.agent_id ? 'active' : ''}" 
             onclick="selectAgent('${agent.agent_id}')">
            <div class="agent-card-header">
                <span class="agent-name">${agent.agent_name || 'Generic Device'}</span>
                <span class="status-dot ${agent.status === 'online' ? 'status-online' : 'status-offline'}"></span>
            </div>
            <div class="agent-meta">${agent.agent_id.substring(0, 15)}...</div>
        </div>
    `).join('');

    if (agentListEl.innerHTML !== newHTML) {
        agentListEl.innerHTML = newHTML;
    }
}

window.selectAgent = (id) => {
    const isNewSelection = selectedAgentId !== id;
    selectedAgentId = id;
    noSelectionEl.classList.add('hidden');

    if (isNewSelection) {
        // Force reflow to restart entrance animation
        dashboardEl.classList.remove('animate-enter');
        void dashboardEl.offsetWidth;
        dashboardEl.classList.add('animate-enter');
    }

    dashboardEl.classList.remove('hidden');
    renderAgentList();
    fetchAgentData(id);

    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 100);
};

function updateDashboard(data) {
    document.getElementById('active-name').innerText = data.agent_name || 'Unnamed';
    document.getElementById('active-id').innerText = '#' + data.agent_id.substring(0, 8);

    document.getElementById('active-last-seen').innerText = data.agent_status.last_seen
        ? new Date(data.agent_status.last_seen).toLocaleTimeString()
        : 'Unknown';

    const sys = data.system_info || {};
    document.getElementById('sys-user').innerText = sys.username || '-';
    document.getElementById('sys-platform').innerText = sys.platform || '-';
    document.getElementById('sys-os').innerText = sys.os_version?.split('(')[0] || '-';
    document.getElementById('sys-ip').innerText = sys.ipv4 || '-';
    document.getElementById('sys-mac').innerText = sys.mac_address || '-';
    document.getElementById('sys-plan').innerText = sys.power_plan || 'Balanced';

    // Battery
    const bat = sys.battery || { percent: 0, charging: false };
    document.getElementById('bat-percent').innerText = `${bat.percent}%`;
    const batFill = document.getElementById('bat-fill');
    batFill.style.width = `${bat.percent}%`;

    if (bat.percent < 20) batFill.style.background = '#ef4444';
    else if (bat.percent < 50) batFill.style.background = '#f59e0b';
    else batFill.style.background = '#10b981';

    document.getElementById('bat-status').innerText = bat.charging ? '● Charging' : '○ Discharging';

    // Location
    const lat = data.agent_status.lat;
    const lon = data.agent_status.lon;
    document.getElementById('active-location-summary').innerText =
        lat && lon ? `${lat.toFixed(3)}, ${lon.toFixed(3)}` : 'No Signal';

    if (lat && lon) {
        updateMap(lat, lon);
    }

    // Location History
    const history = data.location_history || [];
    const historyEl = document.getElementById('location-history');
    if (history.length > 0) {
        historyEl.innerHTML = history.slice(-6).reverse().map(h => `
            <li class="history-item">
                <span>${new Date(h.timestamp || h.time).toLocaleTimeString()}</span>
                <b class="geo-badge">${(h.lat || 0).toFixed(3)}, ${(h.lon || 0).toFixed(3)}</b>
            </li>
        `).join('');
    } else {
        historyEl.innerHTML = '<li class="empty-list">No history recorded yet.</li>';
    }

    lucide.createIcons();
}

// Map (unchanged)
function updateMap(lat, lon) {
    if (!map) {
        map = L.map('map', { zoomControl: false }).setView([lat, lon], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; CartoDB'
        }).addTo(map);
        L.control.zoom({ position: 'bottomright' }).addTo(map);
    }

    if (!currentMarker) {
        currentMarker = L.circleMarker([lat, lon], {
            radius: 9,
            fillColor: "#3b82f6",
            color: "#fff",
            weight: 2,
            opacity: 1,
            fillOpacity: 1
        }).addTo(map);
    } else {
        currentMarker.setLatLng([lat, lon]);
    }

    map.panTo([lat, lon]);
}

// Power Commands (unchanged - but using correct header now via apiCall)
document.querySelectorAll('.ctrl-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const cmd = btn.dataset.cmd;
        if (!selectedAgentId) return;

        if (confirm(`Authorize remote command: ${cmd.toUpperCase()}?`)) {
            const res = await apiCall(`/agents/${selectedAgentId}/power_options/${cmd}`, 'POST');

            if (res && res.status === 'success') {
                showToast(`Command ${cmd} sent successfully`, 'success');
            } else {
                showToast(`Failed to send ${cmd}`, 'error');
            }
        }
    });
});

function showToast(msg, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    // You can add a nice toast UI later if you want
}

// Search
document.getElementById('agent-search').addEventListener('input', renderAgentList);

// Boot
init();
