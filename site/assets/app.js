
const toNumber = (id) => parseFloat(document.getElementById(id).value || 0);
const basePath = document.querySelector('meta[name="base-path"]')?.getAttribute('content') || '';

function isaTemp(altFt) { return 15 - 2 * (altFt / 1000); }

document.addEventListener('click', (event) => {
  const action = event.target.getAttribute('data-action');
  if (!action) return;

  if (action === 'calc-isa') {
    const alt = toNumber('isa-alt');
    const oat = toNumber('isa-oat');
    const isa = isaTemp(alt);
    const dev = (oat - isa).toFixed(1);
    document.getElementById('isa-output').textContent = `ISA temp: ${isa.toFixed(1)}°C | ISA deviation: ${dev}°C`;
  }
  if (action === 'calc-altimetry') {
    const elevM = toNumber('alt-elev');
    const qnh = toNumber('alt-qnh');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    document.getElementById('alt-output').textContent = `Pressure altitude: ${pressureAlt.toFixed(0)} ft (${(pressureAlt/3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-da') {
    const elevM = toNumber('da-elev');
    const qnh = toNumber('da-qnh');
    const oat = toNumber('da-oat');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    const isa = isaTemp(pressureAlt);
    const da = pressureAlt + 120 * (oat - isa);
    document.getElementById('da-output').textContent = `Density altitude: ${da.toFixed(0)} ft (${(da/3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-tas') {
    const ias = toNumber('tas-ias');
    const alt = toNumber('tas-alt');
    const dev = toNumber('tas-dev');
    const tas = ias * (1 + alt / 1000 * 0.02) * (1 + dev / 100);
    document.getElementById('tas-output').textContent = `Estimated TAS: ${tas.toFixed(1)} kt (training approximation)`;
  }
  if (action === 'calc-hypoxia') {
    const alt = toNumber('hypoxia-alt');
    const index = Math.max(10, 100 - alt / 300);
    document.getElementById('hypoxia-output').textContent = `Oxygen index: ${index.toFixed(1)} (training scale). Beware trapped gas at altitude.`;
  }
  if (action === 'calc-press') {
    const cruise = toNumber('press-cruise');
    const dest = toNumber('press-dest');
    const rate = toNumber('press-rate');
    const diff = toNumber('press-diff');
    const cabin = Math.min(cruise * 0.6, dest + diff * 2000);
    document.getElementById('press-output').textContent = `Estimated cabin altitude: ${cabin.toFixed(0)} ft at ${rate} fpm (training only)`;
  }
  if (action === 'build-scenario') {
    buildScenarioCard();
  }
});

function filterCards(inputId, selector) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('input', () => {
    const term = input.value.toLowerCase();
    document.querySelectorAll(selector).forEach(card => {
      const text = card.textContent.toLowerCase();
      card.style.display = text.includes(term) ? 'block' : 'none';
    });
  });
}

filterCards('airfield-search', '.card[data-ident]');
filterCards('route-search', '.card[data-route]');

async function buildScenarioCard() {
  const profileId = document.getElementById('scenario-profile').value;
  const airfieldId = document.getElementById('scenario-airfield').value;
  const routeId = document.getElementById('scenario-route').value;
  const aircraftId = document.getElementById('scenario-aircraft').value;

  const latest = await fetch(`${basePath}api/latest.json`).then(r => r.json());
  const profiles = await fetch(`${basePath}api/profiles.json`).then(r => r.json());
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());

  const profile = profiles.find(p => p.name === profileId);
  const aircraftInfo = aircraft.find(a => a.type === aircraftId);
  const airfield = latest.airfields.find(a => a.ident === airfieldId);
  const route = latest.routes.find(r => r.route_id === routeId);

  const output = document.getElementById('scenario-output');
  const title = route ? `Route ${route.route_id}` : `Airfield ${airfield.ident}`;
  const flags = route ? route.summary.flags : airfield.computed.flags;
  const da = airfield ? airfield.computed.density_altitude.da_ft : '—';

  output.innerHTML = `
    <h4>${title}</h4>
    <p><strong>Profile:</strong> ${profile ? profile.name : ''}</p>
    <p><strong>Aircraft:</strong> ${aircraftInfo ? aircraftInfo.type : ''} (${aircraftInfo ? aircraftInfo.demonstrated_crosswind_kt : ''} kt demo crosswind)</p>
    <p><strong>Density altitude:</strong> ${da} ft</p>
    <p><strong>Flags:</strong> ${flags.join(', ') || 'LOW_RISK'}</p>
    <p><strong>Questions:</strong> How will crosswind/tailwind affect your performance? Are you within personal minima?</p>
  `;
}

async function populateScenario() {
  const latest = await fetch(`${basePath}api/latest.json`).then(r => r.json());
  const profiles = await fetch(`${basePath}api/profiles.json`).then(r => r.json());
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());

  const profileSelect = document.getElementById('scenario-profile');
  const airfieldSelect = document.getElementById('scenario-airfield');
  const routeSelect = document.getElementById('scenario-route');
  const aircraftSelect = document.getElementById('scenario-aircraft');

  if (profileSelect) {
    profiles.forEach(p => profileSelect.add(new Option(p.name, p.name)));
    latest.airfields.forEach(a => airfieldSelect.add(new Option(a.ident, a.ident)));
    latest.routes.forEach(r => routeSelect.add(new Option(r.route_id, r.route_id)));
    aircraft.forEach(a => aircraftSelect.add(new Option(a.type, a.type)));
  }
}

populateScenario();

async function populateAircraft() {
  const container = document.getElementById('aircraft-list');
  if (!container) return;
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());
  container.innerHTML = aircraft.map(a => `<div class="card"><h4>${a.type}</h4><p>Demo crosswind: ${a.demonstrated_crosswind_kt} kt</p><p>${a.notes}</p></div>`).join('');
}

populateAircraft();

function renderSparkline() {
  document.querySelectorAll('[data-spark]').forEach(el => {
    const data = JSON.parse(el.getAttribute('data-spark'));
    if (!data.length) return;
    const max = Math.max(...data.filter(v => v !== null));
    const min = Math.min(...data.filter(v => v !== null));
    const width = 140;
    const height = 40;
    const points = data.map((v, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((v - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    }).join(' ');
    el.innerHTML = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><polyline fill="none" stroke="#0ea5e9" stroke-width="2" points="${points}"/></svg>`;
  });
}

renderSparkline();
