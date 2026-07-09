/* ============================================================
   Rumain Dashboard — app.js
   WebSocket client · 3D particle background · Agent state UI
   ============================================================ */

'use strict';

// ── Constants ─────────────────────────────────────────────────
const WS_URL   = `ws://${location.host}/ws`;
const API_BASE = `http://${location.host}`;
const MAX_LOG  = 80;

// ── State ──────────────────────────────────────────────────────
let ws             = null;
let wsRetries      = 0;
let commandCount   = 0;
let waveAnimId     = null;
let currentOrbState = 'idle';    // idle | listening | thinking | speaking

// ── DOM refs ───────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const wsStatusEl   = $('ws-status');
const wsTextEl     = $('ws-status-text');
const orbCore      = $('orb-core');
const orbIcon      = $('orb-icon');
const orbStateEl   = $('orb-state');
const logFeed      = $('log-feed');
const cmdInput     = $('cmd-input');
const waveform     = $('waveform');
const waveBars     = Array.from(waveform.querySelectorAll('.wave-bar'));

// Agent card refs
const agentCards = {
  ear:   { card: $('agent-ear'),   fill: $('ear-fill'),   state: $('ear-state')   },
  mind:  { card: $('agent-mind'),  fill: $('mind-fill'),  state: $('mind-state')  },
  hand:  { card: $('agent-hand'),  fill: $('hand-fill'),  state: $('hand-state')  },
  voice: { card: $('agent-voice'), fill: $('voice-fill'), state: $('voice-state') },
};

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('start-time').textContent = formatTime(new Date());
  initThreeBackground();
  initOrbGalaxy();
  connectWS();
  pollSystemStats();
  setOrbState('idle');

  // Orb click → test command
  orbCore.addEventListener('click', e => {
    spawnRipple(e.clientX, e.clientY);
    const demo = ['open notepad','system status','what time is it','search for weather today'];
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
      addLog('info', `Workflow: ${msg.status}`);
      break;

    case 'api_command':
      addLog('command', `▶ ${msg.command}`);
      break;
  }
}

// ── Agent State Machine ────────────────────────────────────────
function updateAgentState(agent, state) {
  const ref = agentCards[agent];
  if (!ref) return;

  // Remove all state classes
  ref.card.classList.remove('active','success','error','sleeping');

  if (state === 'running') {
    ref.card.classList.add('active');
    updateOrbForAgent(agent);
  } else if (state === 'success') {
    ref.card.classList.add('success');
  } else if (state === 'error') {
    ref.card.classList.add('error');
  }

  ref.state.textContent = state;
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
    $('last-transcript').textContent = `"${msg.payload}"`;
    commandCount++;
    updateCommandStat();
  }
}

function handleSpeech(msg) {
  $('last-response').textContent = msg.message;
  $('intent-badge').textContent  = msg.intent || '—';
  addLog(msg.success ? 'response' : 'error', '🔊 ' + msg.message);
  setOrbState('speaking');
  
  // Speak "openly" in the browser
  if ('speechSynthesis' in window) {
    const speakMessage = () => {
      const utterance = new SpeechSynthesisUtterance(msg.message);
      utterance.rate = 1.05;
      utterance.pitch = 1.3; // Higher pitch for younger female voice
      
      const voices = window.speechSynthesis.getVoices();
      // Target names like Zira, Google UK English Female, or Samantha
      const femaleVoice = voices.find(v => 
        v.lang.startsWith('en') && 
        (v.name.includes('Female') || v.name.includes('Zira') || v.name.includes('Samantha') || v.name.includes('Victoria'))
      );
      if (femaleVoice) utterance.voice = femaleVoice;

      utterance.onend = () => setOrbState('idle');
      utterance.onerror = () => setOrbState('idle');
      window.speechSynthesis.speak(utterance);
    };

    // If voices aren't loaded yet, wait for them
    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        speakMessage();
      };
    } else {
      speakMessage();
    }
  } else {
    setTimeout(() => setOrbState('idle'), 3000);
  }
}

// ── Web Speech API (Push to Talk) ──────────────────────────────
let webSpeechRec = null;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  webSpeechRec = new SpeechRecognition();
  webSpeechRec.continuous = false;
  webSpeechRec.interimResults = false;
  webSpeechRec.lang = 'en-US';

  webSpeechRec.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    addLog('info', `🎤 Heard: "${transcript}"`);
    injectCommand(transcript);
  };

  webSpeechRec.onerror = (event) => {
    addLog('error', `Microphone error: ${event.error}`);
    setOrbState('idle');
  };
  
  webSpeechRec.onend = () => {
    $('ptt-btn').style.transform = 'scale(1)';
    $('ptt-btn').style.boxShadow = '';
  };
}

function toggleWebSpeech() {
  if (!webSpeechRec) {
    addLog('error', 'Web Speech API is not supported in this browser.');
    return;
  }
  if (currentOrbState === 'listening') {
    try { webSpeechRec.stop(); } catch(e) {}
    return;
  }
  try {
    webSpeechRec.start();
    setOrbState('listening');
    $('ptt-btn').style.transform = 'scale(0.9)';
    $('ptt-btn').style.boxShadow = 'inset 0 0 10px rgba(0,0,0,0.5)';
  } catch(e) {}
}

// expose to global
window.toggleWebSpeech = toggleWebSpeech;

// ── Orb State ──────────────────────────────────────────────────
function setOrbState(state) {
  currentOrbState = state;
  orbCore.classList.remove('listening','thinking','speaking');

  const stateMap = {
    idle:      { icon:'🌀', label:'Waiting for "Hey Rumain"', cls:null },
    listening: { icon:'👂', label:'Listening…',               cls:'listening' },
    thinking:  { icon:'🧠', label:'Thinking…',               cls:'thinking' },
    speaking:  { icon:'🔊', label:'Speaking…',                cls:'speaking' },
  };

  const s = stateMap[state] || stateMap.idle;
  if (orbIcon) orbIcon.textContent = s.icon;
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
        ? 6 + Math.random() * 32
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
  el.innerHTML = `<span class="log-time">${formatTime(new Date())}</span>${escHtml(text)}`;
  logFeed.appendChild(el);
  // Trim
  while (logFeed.children.length > MAX_LOG) logFeed.removeChild(logFeed.firstChild);
  logFeed.scrollTop = logFeed.scrollHeight;
}

function clearLog() {
  logFeed.innerHTML = '';
  addLog('info', 'Log cleared.');
}

// ── Manual command ─────────────────────────────────────────────
async function sendCommand() {
  const text = cmdInput.value.trim();
  if (!text) return;
  cmdInput.value = '';
  await injectCommand(text);
}

async function injectCommand(text) {
  addLog('command', `▶ ${text}`);
  setOrbState('thinking');
  try {
    const res = await fetch(`${API_BASE}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    addLog('error', `Could not send command: ${e.message}`);
    setOrbState('idle');
  }
}

// make sendCommand / clearLog global for onclick handlers
window.sendCommand = sendCommand;
window.clearLog    = clearLog;

// ── System Stats Polling ───────────────────────────────────────
async function pollSystemStats() {
  await fetchStats();
  setInterval(fetchStats, 8000);
}

async function fetchStats() {
  try {
    const res  = await fetch(`${API_BASE}/status`);
    const data = await res.json();
    if (data.agents) {
      Object.entries(data.agents).forEach(([name, state]) => updateAgentState(name, state));
    }
  } catch { /* server not ready yet */ }
}

function updateCommandStat() {
  $('stat-cmds').textContent = commandCount;
  const pct = Math.min(100, commandCount * 5);
  $('cmd-bar').style.width = pct + '%';
}

// ── WebSocket Status UI ────────────────────────────────────────
function setWsStatus(online) {
  wsStatusEl.className = `status-badge ${online ? 'online' : 'offline'}`;
  wsTextEl.textContent  = online ? 'Connected' : 'Offline';
}

// ── Ripple effect ──────────────────────────────────────────────
function spawnRipple(x, y) {
  const r = document.createElement('div');
  r.className = 'ripple';
  r.style.left = x + 'px';
  r.style.top  = y + 'px';
  document.body.appendChild(r);
  r.addEventListener('animationend', () => r.remove());
}

// ── Utilities ──────────────────────────────────────────────────
function formatTime(d) {
  return d.toLocaleTimeString('en-US', { hour12: true, hour:'2-digit', minute:'2-digit', second:'2-digit' });
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Three.js Particle Background ──────────────────────────────
function initThreeBackground() {
  const canvas = $('bg-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2000);
  camera.position.z = 600;

  // ── Galaxy Background ──────────────────────────────────────────────
  const COUNT  = 2000;
  const geo    = new THREE.BufferGeometry();
  const pos    = new Float32Array(COUNT * 3);
  const colors = new Float32Array(COUNT * 3);
  const palette = [
    [0.9, 0.9, 1.0],  // White star
    [0.545, 0.361, 0.965],  // violet
    [0.063, 0.725, 0.506],  // emerald
    [0.149, 0.392, 0.922],  // blue
    [1.0, 0.8, 0.4],  // warm star
  ];

  for (let i = 0; i < COUNT; i++) {
    // Spiral galaxy distribution
    const radius = Math.random() * 800;
    const spinAngle = radius * 0.005;
    const branchAngle = ((i % 3) / 3) * Math.PI * 2;
    const randomAngle = branchAngle + spinAngle + (Math.random() - 0.5) * 0.5;

    pos[i*3]   = Math.cos(randomAngle) * radius + (Math.random() - 0.5) * 100; // x
    pos[i*3+1] = (Math.random() - 0.5) * 150 * (1 - radius/800);               // y
    pos[i*3+2] = Math.sin(randomAngle) * radius + (Math.random() - 0.5) * 100; // z

    const c = palette[Math.floor(Math.random() * palette.length)];
    colors[i*3]   = c[0];
    colors[i*3+1] = c[1];
    colors[i*3+2] = c[2];
  }

  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color',    new THREE.BufferAttribute(colors, 3));

  const mat = new THREE.PointsMaterial({
    size: 2.5, vertexColors: true, transparent: true, opacity: 0.8,
    sizeAttenuation: true, blending: THREE.AdditiveBlending
  });

  const points = new THREE.Points(geo, mat);
  points.rotation.x = 0.2;
  scene.add(points);

  // ── Falling Stars ──────────────────────────────────────────
  const fallCount = 150;
  const fallGeo = new THREE.BufferGeometry();
  const fallPos = new Float32Array(fallCount * 3);
  const fallSpeeds = new Float32Array(fallCount);
  
  for (let i = 0; i < fallCount; i++) {
    fallPos[i*3] = (Math.random() - 0.5) * 1600; // x
    fallPos[i*3+1] = Math.random() * 800 - 400;   // y
    fallPos[i*3+2] = (Math.random() - 0.5) * 600; // z
    fallSpeeds[i] = 0.8 + Math.random() * 1.5;    // speed
  }
  
  fallGeo.setAttribute('position', new THREE.BufferAttribute(fallPos, 3));
  
  const starTexture = (() => {
    const c = document.createElement('canvas');
    c.width = 16; c.height = 16;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.3, 'rgba(0, 240, 255, 0.8)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 16, 16);
    return new THREE.CanvasTexture(c);
  })();
  
  const fallMat = new THREE.PointsMaterial({
    size: 4.0,
    map: starTexture,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  
  const fallingStars = new THREE.Points(fallGeo, fallMat);
  scene.add(fallingStars);

  // ── Shooting Stars ─────────────────────────────────────────
  const shootCount = 5;
  const shootGeo = new THREE.BufferGeometry();
  const shootPos = new Float32Array(shootCount * 3);
  const shootTarget = [];
  
  const resetShooter = (i) => {
    shootPos[i*3] = (Math.random() - 0.3) * 1600 - 200; // x starts right
    shootPos[i*3+1] = Math.random() * 300 + 300;        // y starts top
    shootPos[i*3+2] = (Math.random() - 0.5) * 400;       // z
    shootTarget[i] = {
      vx: -(8.0 + Math.random() * 12.0), // speed left
      vy: -(8.0 + Math.random() * 12.0), // speed down
      life: 0,
      maxLife: 20 + Math.random() * 30
    };
  };

  for (let i = 0; i < shootCount; i++) {
    resetShooter(i);
  }
  
  shootGeo.setAttribute('position', new THREE.BufferAttribute(shootPos, 3));
  
  const shootMat = new THREE.PointsMaterial({
    size: 5.5,
    map: starTexture,
    transparent: true,
    opacity: 0.95,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  
  const shootingStars = new THREE.Points(shootGeo, shootMat);
  scene.add(shootingStars);

  // ── Mouse Parallax ─────────────────────────────────────────
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - window.innerWidth / 2) * 0.5;
    mouseY = (e.clientY - window.innerHeight / 2) * 0.5;
  });

  // ── Animation loop ─────────────────────────────────────────
  let t = 0;
  const animate = () => {
    requestAnimationFrame(animate);
    t += 0.01;
    
    // Smooth follow mouse
    targetX += (mouseX - targetX) * 0.05;
    targetY += (mouseY - targetY) * 0.05;

    camera.position.x += (targetX - camera.position.x) * 0.02;
    camera.position.y += (-targetY - camera.position.y) * 0.02;
    camera.lookAt(scene.position);

    points.rotation.y += 0.0005;
    points.rotation.x += 0.0001;

    // Animate falling stars
    const fallPositions = fallingStars.geometry.attributes.position.array;
    for (let i = 0; i < fallCount; i++) {
      fallPositions[i*3+1] -= fallSpeeds[i];
      fallPositions[i*3] += Math.sin(t + i) * 0.04; // twinkling drift
      
      if (fallPositions[i*3+1] < -400) {
        fallPositions[i*3+1] = 400;
        fallPositions[i*3] = (Math.random() - 0.5) * 1600;
        fallSpeeds[i] = 0.8 + Math.random() * 1.5;
      }
    }
    fallingStars.geometry.attributes.position.needsUpdate = true;

    // Animate shooting stars
    const shootPositions = shootingStars.geometry.attributes.position.array;
    for (let i = 0; i < shootCount; i++) {
      const tgt = shootTarget[i];
      shootPositions[i*3] += tgt.vx;
      shootPositions[i*3+1] += tgt.vy;
      tgt.life++;
      
      if (tgt.life > tgt.maxLife || shootPositions[i*3+1] < -400) {
        resetShooter(i);
      }
    }
    shootingStars.geometry.attributes.position.needsUpdate = true;

    renderer.render(scene, camera);
  };
  animate();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
}

// ── 3D Galaxy Behind Avatar ──────────────────────────────────
function initOrbGalaxy() {
  const canvas = $('orb-galaxy-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const width = canvas.clientWidth || 500;
  const height = canvas.clientHeight || 500;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
  camera.position.z = 320;

  // ── The Glowing Moon Behind Her ────────────────────────────
  const moonRadius = 60;
  const moonGeo = new THREE.SphereGeometry(moonRadius, 32, 32);
  const moonMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.15,
    wireframe: true
  });
  const moon = new THREE.Mesh(moonGeo, moonMat);
  moon.position.set(0, 0, -85); // Centered and directly behind the avatar
  scene.add(moon);

  // Outer Atmosphere Glow (Cyan/blue halo)
  const glowGeo = new THREE.SphereGeometry(moonRadius + 12, 32, 32);
  const glowMat = new THREE.MeshBasicMaterial({
    color: 0x00f0ff,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide
  });
  const moonGlow = new THREE.Mesh(glowGeo, glowMat);
  moon.add(moonGlow);

  // Inner Solid Brightness
  const solidGeo = new THREE.SphereGeometry(moonRadius - 4, 32, 32);
  const solidMat = new THREE.MeshBasicMaterial({
    color: 0xe0f7fa,
    transparent: true,
    opacity: 0.12,
  });
  const moonSolid = new THREE.Mesh(solidGeo, solidMat);
  moon.add(moonSolid);

  // Custom textures
  const starTexture = (() => {
    const c = document.createElement('canvas');
    c.width = 16; c.height = 16;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.25, 'rgba(255, 235, 255, 0.85)');
    grad.addColorStop(0.6, 'rgba(120, 120, 255, 0.25)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 16, 16);
    return new THREE.CanvasTexture(c);
  })();

  const gasTexture = (() => {
    const c = document.createElement('canvas');
    c.width = 64; c.height = 64;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(200, 100, 255, 0.25)');
    grad.addColorStop(0.3, 'rgba(100, 120, 255, 0.12)');
    grad.addColorStop(0.7, 'rgba(50, 200, 255, 0.03)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();

  // 1. STARS GEOMETRY
  const starCount = 7500;
  const starGeo = new THREE.BufferGeometry();
  const starPos = new Float32Array(starCount * 3);
  const starColors = new Float32Array(starCount * 3);

  // Milky Way colors
  const coreColor = new THREE.Color('#ffe082');   // Bright yellowish white core
  const midColor = new THREE.Color('#d1c4e9');    // Soft violet
  const outerColor = new THREE.Color('#00e5ff');  // Electric cyan outer
  const pinkColor = new THREE.Color('#ff4081');   // Hot pink spurs

  for (let i = 0; i < starCount; i++) {
    let r, x, y, z;
    const isCore = Math.random() < 0.35; // Core bulge vs spiral arms

    if (isCore) {
      // Core bulge (spherical clump)
      r = Math.pow(Math.random(), 1.5) * 55;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);
      x = r * Math.sin(phi) * Math.cos(theta);
      y = r * Math.sin(phi) * Math.sin(theta) * 0.7; // slightly flattened
      z = r * Math.cos(phi);
    } else {
      // Spiral arms (2 main arms, 2 minor spurs)
      r = 55 + Math.pow(Math.random(), 2.0) * 165;
      const numArms = 2;
      const armIndex = i % numArms;
      const armAngle = (armIndex / numArms) * Math.PI * 2;
      const twist = 0.022; // twisting rate
      const angle = armAngle + r * twist + (Math.random() - 0.5) * 0.28;

      const thickness = Math.max(2, 28 * (1 - r / 220));
      x = Math.cos(angle) * r + (Math.random() - 0.5) * thickness;
      y = (Math.random() - 0.5) * thickness * 0.3 + (Math.random() - 0.5) * 4;
      z = Math.sin(angle) * r + (Math.random() - 0.5) * thickness;
    }

    starPos[i * 3] = x;
    starPos[i * 3 + 1] = y;
    starPos[i * 3 + 2] = z;

    // Color grading based on radial distance
    const dist = Math.sqrt(x*x + y*y + z*z);
    let mixedColor;
    if (dist < 45) {
      mixedColor = coreColor.clone().lerp(new THREE.Color('#ffffff'), dist / 45);
    } else if (dist < 120) {
      mixedColor = new THREE.Color('#ffffff').lerp(midColor, (dist - 45) / 75);
    } else {
      const isPink = i % 3 === 0;
      mixedColor = isPink 
        ? midColor.clone().lerp(pinkColor, (dist - 120) / 100)
        : midColor.clone().lerp(outerColor, (dist - 120) / 100);
    }

    starColors[i * 3] = mixedColor.r;
    starColors[i * 3 + 1] = mixedColor.g;
    starColors[i * 3 + 2] = mixedColor.b;
  }

  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
  starGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

  const starMat = new THREE.PointsMaterial({
    size: 2.2,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
    map: starTexture,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  const starPoints = new THREE.Points(starGeo, starMat);
  scene.add(starPoints);

  // 2. NEBULA GAS CLOUDS GEOMETRY
  const gasCount = 600;
  const gasGeo = new THREE.BufferGeometry();
  const gasPos = new Float32Array(gasCount * 3);
  const gasColors = new Float32Array(gasCount * 3);

  const gasCyan = new THREE.Color('#00bcd4');
  const gasPurple = new THREE.Color('#8e24aa');
  const gasPink = new THREE.Color('#e91e63');

  for (let i = 0; i < gasCount; i++) {
    // Gas follows the spiral arms closely
    const r = 20 + Math.pow(Math.random(), 1.8) * 180;
    const numArms = 2;
    const armIndex = i % numArms;
    const armAngle = (armIndex / numArms) * Math.PI * 2;
    const twist = 0.022;
    const angle = armAngle + r * twist + (Math.random() - 0.5) * 0.42;

    const thickness = Math.max(8, 38 * (1 - r / 200));
    const x = Math.cos(angle) * r + (Math.random() - 0.5) * thickness;
    const y = (Math.random() - 0.5) * thickness * 0.25;
    const z = Math.sin(angle) * r + (Math.random() - 0.5) * thickness;

    gasPos[i * 3] = x;
    gasPos[i * 3 + 1] = y;
    gasPos[i * 3 + 2] = z;

    // Alternating nebulous colors
    let col;
    if (r < 60) {
      col = gasPurple.clone().lerp(new THREE.Color('#ffb74d'), 0.4); // dusty warm inner
    } else {
      col = i % 2 === 0 ? gasCyan : gasPink;
    }

    gasColors[i * 3] = col.r;
    gasColors[i * 3 + 1] = col.g;
    gasColors[i * 3 + 2] = col.b;
  }

  gasGeo.setAttribute('position', new THREE.BufferAttribute(gasPos, 3));
  gasGeo.setAttribute('color', new THREE.BufferAttribute(gasColors, 3));

  const gasMat = new THREE.PointsMaterial({
    size: 26,
    vertexColors: true,
    transparent: true,
    opacity: 0.28,
    map: gasTexture,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  const gasPoints = new THREE.Points(gasGeo, gasMat);
  scene.add(gasPoints);

  // Group to rotate everything together
  const galaxyGroup = new THREE.Group();
  galaxyGroup.add(starPoints);
  galaxyGroup.add(gasPoints);
  
  // Angle it beautifully in 3D
  galaxyGroup.rotation.x = 1.25; // Tilted disk
  galaxyGroup.rotation.z = 0.55;
  scene.add(galaxyGroup);

  // Mouse Parallax variables
  let targetRotationX = 1.25;
  let targetRotationY = 0.0;
  let mouseX = 0, mouseY = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
    mouseY = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
  });

  // Animation Loop
  const animate = () => {
    requestAnimationFrame(animate);

    // Slowly spin the entire galaxy
    galaxyGroup.rotation.y += 0.0022;

    // Rotate the moon
    moon.rotation.y += 0.0015;
    moon.rotation.x += 0.0007;

    // Gentle floating movement to make it feel like it's suspended in space
    const floatTime = Date.now() * 0.001;
    galaxyGroup.position.y = Math.sin(floatTime) * 4;
    moon.position.y = Math.sin(floatTime) * 2.5;

    // Apply smooth mouse parallax tilting
    targetRotationX = 1.25 + mouseY * 0.18;
    targetRotationY = mouseX * 0.18;

    galaxyGroup.rotation.x += (targetRotationX - galaxyGroup.rotation.x) * 0.05;
    galaxyGroup.rotation.z += (targetRotationY - galaxyGroup.rotation.z) * 0.05;

    renderer.render(scene, camera);
  };
  animate();

  const resize = () => {
    const w = canvas.clientWidth || 500;
    const h = canvas.clientHeight || 500;
    renderer.setSize(w, h);
  };
  window.addEventListener('resize', resize);
}

// ── 3D Card Hover Tilt Effect ─────────────────────────────────
function init3DTilt() {
  const cards = document.querySelectorAll('.agent-card');
  cards.forEach(card => {
    card.addEventListener('mousemove', e => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -10; // Max rotation 10deg
      const rotateY = ((x - centerX) / centerX) * 10;
      
      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
      card.style.transition = 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
    });
    
    card.addEventListener('mouseenter', () => {
      card.style.transition = 'transform 0.1s ease';
    });
  });
}

// Initialize tilt after DOM load
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(init3DTilt, 500);
});
