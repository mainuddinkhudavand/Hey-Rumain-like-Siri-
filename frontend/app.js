/* ============================================================
   Rumain Dashboard — app.js
   WebSocket client · 3D Starfield & Galaxy · 3D Card Hover Tilt
   ============================================================ */

'use strict';

// ── Constants ─────────────────────────────────────────────────
const WS_URL   = `ws://${location.host}/ws`;
const API_BASE = `http://${location.host}`;
const MAX_LOG  = 120;

// ── State ──────────────────────────────────────────────────────
let ws             = null;
let wsRetries      = 0;
let waveAnimId     = null;
let currentOrbState = 'idle';    // idle | listening | thinking | speaking

// ── DOM refs ───────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const wsStatusEl   = $('ws-status');
const wsTextEl     = $('ws-status-text');
const orbCore      = $('orb-core');
const orbStateEl   = $('orb-state');
const logFeed      = $('log-feed');
const cmdInput     = $('cmd-input');
const waveform     = $('waveform');
const waveBars     = Array.from(waveform.querySelectorAll('.wave-bar'));

// Panels for 3D parallax
const avatarPanel  = $('avatar-panel');
const logPanel     = $('log-panel');

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('start-time').textContent = formatTime(new Date());
  
  // Initialize 3D elements
  initThreeBackground();
  initOrbGalaxy();
  init3DLayoutTilt();
  
  // Establish WS Connection
  connectWS();
  
  // Initial states
  setOrbState('idle');
  
  // Test command by clicking avatar frame
  orbCore.addEventListener('click', e => {
    spawnRipple(e.clientX, e.clientY);
    const demo = ['open notepad', 'system status', 'what time is it', 'volume up'];
    const pick = demo[Math.floor(Math.random() * demo.length)];
    injectCommand(pick);
  });
});

// ── WebSocket ──────────────────────────────────────────────────
function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsRetries = 0;
    setWsStatus(true);
    addLog('info', 'Connected to Rumain backend.');
    setOrbState('idle');
  };

  ws.onmessage = ({ data }) => {
    try { handleMessage(JSON.parse(data)); }
    catch (e) { console.warn('WS parse error', e); }
  };

  ws.onclose = () => {
    setWsStatus(false);
    setOrbState('idle');
    addLog('error', 'Connection lost. Reconnecting…');
    const delay = Math.min(5000, 1000 * (wsRetries++ + 1));
    setTimeout(connectWS, delay);
  };

  ws.onerror = () => ws.close();
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'agent_state':
      updateAgentState(msg.agent, msg.state);
      break;

    case 'pipeline_event':
      handlePipelineEvent(msg);
      break;

    case 'speech':
      handleSpeech(msg);
      break;

    case 'error':
      addLog('error', `[${msg.agent}] ${msg.message}`);
      setOrbState('idle');
      break;

    case 'workflow':
      addLog('info', `Workflow Status: ${msg.status}`);
      break;

    case 'api_command':
      addLog('command', msg.command);
      break;
  }
}

// ── Agent State Machine ────────────────────────────────────────
function updateAgentState(agent, state) {
  if (state === 'running') {
    updateOrbForAgent(agent);
  } else if (state === 'success' && agent === 'voice') {
    setOrbState('idle');
  }
}

function updateOrbForAgent(agent) {
  const stateMap = {
    ear:   'listening',
    mind:  'thinking',
    hand:  'thinking',
    voice: 'speaking',
  };
  setOrbState(stateMap[agent] || 'idle');
}

function handlePipelineEvent(msg) {
  if (msg.source === 'ear' || msg.source === 'api') {
    addLog('command', msg.payload);
  }
}

function handleSpeech(msg) {
  addLog(msg.success ? 'response' : 'error', msg.message);
  setOrbState('speaking');
}

// ── Web Speech API (Push to TalkFallback) ──────────────────────
let webSpeechRec = null;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  webSpeechRec = new SpeechRecognition();
  webSpeechRec.continuous = false;
  webSpeechRec.interimResults = false;
  webSpeechRec.lang = 'en-US';

  webSpeechRec.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    injectCommand(transcript);
  };

  webSpeechRec.onerror = (event) => {
    addLog('error', `Microphone error: ${event.error}`);
    setOrbState('idle');
  };
  
  webSpeechRec.onend = () => {
    $('ptt-btn').classList.remove('active');
  };
}

function toggleWebSpeech() {
  if (!webSpeechRec) {
    addLog('error', 'Browser Speech API not supported. Use text fallback.');
    return;
  }
  if (currentOrbState === 'listening') {
    try { webSpeechRec.stop(); } catch(e) {}
    return;
  }
  try {
    webSpeechRec.start();
    setOrbState('listening');
    $('ptt-btn').classList.add('active');
  } catch(e) {}
}

window.toggleWebSpeech = toggleWebSpeech;

// ── Orb State ──────────────────────────────────────────────────
function setOrbState(state) {
  currentOrbState = state;
  orbCore.className = 'avatar-frame-3d'; // Reset classes

  const stateMap = {
    idle:      { label: 'Say "Hey Rumain"', cls: null },
    listening: { label: 'Listening…',       cls: 'listening' },
    thinking:  { label: 'Thinking…',        cls: 'thinking' },
    speaking:  { label: 'Speaking…',        cls: 'speaking' },
  };

  const s = stateMap[state] || stateMap.idle;
  orbStateEl.textContent = s.label;
  if (s.cls) orbCore.classList.add(s.cls);

  animateWaveform(state !== 'idle');
}

// ── Waveform animation ─────────────────────────────────────────
function animateWaveform(active) {
  if (waveAnimId) { cancelAnimationFrame(waveAnimId); waveAnimId = null; }
  if (!active) {
    waveBars.forEach((b, i) => b.style.height = `${[6,14,8,22,10,30,18,12,26,8,20,14,6][i] || 10}px`);
    return;
  }
  const animate = () => {
    waveBars.forEach(b => {
      const h = currentOrbState === 'speaking'
        ? 6 + Math.random() * 38
        : 4 + Math.random() * 18;
      b.style.height = `${h}px`;
    });
    waveAnimId = requestAnimationFrame(animate);
  };
  animate();
}

// ── Log Feed ───────────────────────────────────────────────────
function addLog(type, text) {
  const el = document.createElement('div');
  el.className = `log-entry ${type}`;
  
  let labelText = text;
  if (type === 'command') {
    labelText = `🙋 User: "${text}"`;
  } else if (type === 'response') {
    labelText = `🤖 Rumain: "${text}"`;
  }
  
  el.innerHTML = `<span class="log-time">${formatTime(new Date())}</span>${escHtml(labelText)}`;
  logFeed.appendChild(el);
  
  // Trim excessive history to save RAM
  while (logFeed.children.length > MAX_LOG) {
    logFeed.removeChild(logFeed.firstChild);
  }
  logFeed.scrollTop = logFeed.scrollHeight;
}

function clearLog() {
  logFeed.innerHTML = '';
  addLog('info', 'Console logs cleared.');
}

window.clearLog = clearLog;

// ── Manual command injection ──────────────────────────────────
async function sendCommand() {
  const text = cmdInput.value.trim();
  if (!text) return;
  cmdInput.value = '';
  await injectCommand(text);
}

async function injectCommand(text) {
  setOrbState('thinking');
  try {
    const res = await fetch(`${API_BASE}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    addLog('error', `Command delivery failed: ${e.message}`);
    setOrbState('idle');
  }
}

window.sendCommand = sendCommand;

// ── Helper Utilities ──────────────────────────────────────────
function formatTime(d) {
  return d.toLocaleTimeString('en-US', { hour12: true, hour:'2-digit', minute:'2-digit', second:'2-digit' });
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setWsStatus(online) {
  wsStatusEl.className = `status-badge ${online ? 'online' : 'offline'}`;
  wsTextEl.textContent  = online ? 'System Online' : 'System Offline';
}

function spawnRipple(x, y) {
  const r = document.createElement('div');
  r.className = 'ripple';
  r.style.left = x + 'px';
  r.style.top  = y + 'px';
  document.body.appendChild(r);
  r.addEventListener('animationend', () => r.remove());
}

// ── 3D Layout Parallax Tilt ──────────────────────────────────
function init3DLayoutTilt() {
  const body = document.body;
  body.addEventListener('mousemove', e => {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;

    // Small rotating angle for the panels to create a 3D hologram effect
    const rx = (dy / cy) * -8;  // Tilt up/down
    const ry = (dx / cx) * 8;   // Tilt left/right

    avatarPanel.style.transform = `rotateY(${5 + ry}deg) rotateX(${5 + rx}deg) translateZ(10px)`;
    logPanel.style.transform = `rotateY(${-5 + ry}deg) rotateX(${5 + rx}deg) translateZ(10px)`;
  });
  
  body.addEventListener('mouseleave', () => {
    avatarPanel.style.transform = 'rotateY(5deg) rotateX(0deg) translateZ(10px)';
    logPanel.style.transform = 'rotateY(-5deg) rotateX(0deg) translateZ(10px)';
  });
}

// ── Three.js Fullscreen Starfield ───────────────────────────
function initThreeBackground() {
  const canvas = $('bg-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(65, window.innerWidth / window.innerHeight, 1, 2000);
  camera.position.z = 800;

  // Star points
  const count = 1800;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  
  const palette = [
    [0.9, 0.9, 1.0], // white stars
    [0.55, 0.36, 0.96], // violet
    [0.0, 0.94, 1.0], // cyan
  ];

  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 2000;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 2000;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 1500;

    const c = palette[Math.floor(Math.random() * palette.length)];
    colors[i * 3] = c[0];
    colors[i * 3 + 1] = c[1];
    colors[i * 3 + 2] = c[2];
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 2.0,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending
  });

  const starfield = new THREE.Points(geometry, material);
  scene.add(starfield);

  // Animation Loop
  const animate = () => {
    requestAnimationFrame(animate);
    starfield.rotation.y += 0.0003;
    starfield.rotation.x += 0.0001;
    renderer.render(scene, camera);
  };
  animate();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
}

// ── Three.js Avatar Galaxy ───────────────────────────────────
function initOrbGalaxy() {
  const canvas = $('orb-galaxy-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const w = 400;
  const h = 400;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(w, h);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
  camera.position.z = 280;

  // Star texture
  const starTexture = (() => {
    const c = document.createElement('canvas');
    c.width = 16; c.height = 16;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.3, 'rgba(0, 240, 255, 0.85)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 16, 16);
    return new THREE.CanvasTexture(c);
  })();

  // Galaxy Arms
  const count = 4000;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  const innerColor = new THREE.Color('#b026ff'); // Purple core
  const outerColor = new THREE.Color('#00f0ff'); // Cyan outer

  for (let i = 0; i < count; i++) {
    const r = Math.pow(Math.random(), 2.0) * 120 + 5;
    const spin = r * 0.025;
    const armAngle = ((i % 2) * Math.PI) + spin + (Math.random() - 0.5) * 0.25;

    const x = Math.cos(armAngle) * r;
    const y = (Math.random() - 0.5) * 12 * (1 - r / 125);
    const z = Math.sin(armAngle) * r;

    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;

    // Gradient transition
    const mixed = innerColor.clone().lerp(outerColor, r / 125);
    colors[i * 3] = mixed.r;
    colors[i * 3 + 1] = mixed.g;
    colors[i * 3 + 2] = mixed.b;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 2.5,
    map: starTexture,
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  const galaxy = new THREE.Points(geometry, material);
  galaxy.rotation.x = 1.3; // Angle the disk towards viewer
  scene.add(galaxy);

  // Animation Loop
  const animate = () => {
    requestAnimationFrame(animate);
    galaxy.rotation.z += 0.0035; // Spin galaxy
    renderer.render(scene, camera);
  };
  animate();
}
