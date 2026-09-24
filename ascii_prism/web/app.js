/*
 * ASCII Prism browser client.
 *
 * The page captures the webcam, sends one JPEG frame at a time to the Python
 * server over a WebSocket, and draws whatever comes back. Only one frame is
 * in flight, so the stream naturally runs at whatever rate the server can
 * process. Settings live in localStorage and are pushed to the server on
 * connect and whenever they change.
 *
 * Layout: the video fills the page, a dock at the bottom opens one panel at
 * a time, and a readout in the top bar shows tracking state.
 */
(() => {
  'use strict';

  const STORAGE_KEY = 'ascii-prism.settings.v3';
  const JPEG_QUALITY = 0.8;
  const NATURAL_RADIUS = 0.7; // where saturation 100% sits on the colour wheel

  const PANEL_KEYS = {
    characters: ['charset_id', 'charset', 'invert'],
    grid: ['columns'],
    colour: ['saturation', 'hue', 'brightness', 'opacity', 'background'],
    tracking: ['smoothing', 'show_tips', 'mirror'],
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    video: $('video'),
    view: $('view'),
    hint: $('hint'),
    notice: $('notice'),
    connDot: $('conn-dot'),
    connText: $('conn-text'),
    readoutHands: $('readout-hands'),
    readoutGrid: $('readout-grid'),
    readoutPerf: $('readout-perf'),
    dock: $('dock'),
    lock: $('lock'),
    fullscreen: $('fullscreen'),
    unhide: $('unhide'),
    presets: $('presets'),
    charset: $('charset'),
    charsetCount: $('charset-count'),
    invert: $('invert'),
    columns: $('columns'),
    columnsValue: $('columns-value'),
    rowsNote: $('rows-note'),
    wheel: $('wheel'),
    wheelCanvas: $('wheel-canvas'),
    wheelHandle: $('wheel-handle'),
    hueValue: $('hue-value'),
    saturationValue: $('saturation-value'),
    opacity: $('opacity'),
    opacityValue: $('opacity-value'),
    brightness: $('brightness'),
    brightnessValue: $('brightness-value'),
    background: $('background'),
    backgroundValue: $('background-value'),
    smoothing: $('smoothing'),
    smoothingValue: $('smoothing-value'),
    showTips: $('show-tips'),
    mirror: $('mirror'),
  };
  const tools = Array.from(els.dock.querySelectorAll('[data-panel]'));
  const panels = Object.fromEntries(Object.keys(PANEL_KEYS).map((name) => [name, $(`panel-${name}`)]));

  let config = null;
  let settings = null;
  let ws = null;
  let ready = false;
  let inFlight = false;
  let locked = false;
  let cameraOk = false;
  let reconnectDelay = 1000;
  let lastFps = 0;
  const capture = document.createElement('canvas');
  const viewCtx = els.view.getContext('2d');
  let framesShown = 0;
  let fpsWindowStart = performance.now();

  // ------------------------------------------------------------ settings
  function loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      /* private mode etc. */
    }
  }

  function sendSettings() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'settings', settings }));
    }
  }

  function changed() {
    saveSettings();
    sendSettings();
  }

  function levels() {
    return Array.from(settings.charset || ' ').length;
  }

  const percent = (v) => `${Math.round(v * 100)}%`;
  const degrees = (v) => `${v >= 0 ? '+' : '−'}${Math.abs(Math.round(v))}°`;

  // -------------------------------------------------------------- panels
  function openPanel(name) {
    for (const tool of tools) {
      const active = tool.dataset.panel === name;
      tool.setAttribute('aria-expanded', String(active));
      panels[tool.dataset.panel].hidden = !active;
    }
    if (name === 'colour') paintWheel();
  }

  function currentPanel() {
    const tool = tools.find((t) => t.getAttribute('aria-expanded') === 'true');
    return tool ? tool.dataset.panel : null;
  }

  function closePanels() {
    openPanel(null);
  }

  function setChromeHidden(hidden) {
    document.body.classList.toggle('chrome-hidden', hidden);
    els.unhide.hidden = !hidden;
    if (hidden) closePanels();
  }

  // ------------------------------------------------------------------ ui
  function buildUi() {
    const presetIds = [...config.charsets.map((cs) => cs.id), 'custom'];
    for (const id of presetIds) {
      const cs = config.charsets.find((c) => c.id === id);
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.preset = id;
      button.setAttribute('role', 'radio');
      button.setAttribute('aria-checked', 'false');
      button.textContent = cs ? cs.label : 'Custom';
      if (cs) button.title = cs.chars;
      button.addEventListener('click', () => {
        settings.charset_id = id;
        if (cs) settings.charset = cs.chars;
        syncUi();
        changed();
        if (!cs) els.charset.focus();
      });
      els.presets.appendChild(button);
    }

    const r = config.ranges;
    [els.columns.min, els.columns.max] = r.columns;
    [els.smoothing.min, els.smoothing.max] = r.smoothing;
    [els.opacity.min, els.opacity.max] = r.opacity;
    [els.brightness.min, els.brightness.max] = r.brightness;

    els.charset.addEventListener('input', () => {
      settings.charset = els.charset.value || ' ';
      settings.charset_id = 'custom';
      syncPresets();
      els.charsetCount.textContent = String(levels());
      changed();
    });
    els.invert.addEventListener('change', () => { settings.invert = els.invert.checked; changed(); });
    els.columns.addEventListener('input', () => {
      settings.columns = Number(els.columns.value);
      els.columnsValue.value = String(settings.columns);
      changed();
    });
    els.opacity.addEventListener('input', () => {
      settings.opacity = Number(els.opacity.value);
      els.opacityValue.value = percent(settings.opacity);
      changed();
    });
    els.brightness.addEventListener('input', () => {
      settings.brightness = Number(els.brightness.value);
      els.brightnessValue.value = percent(settings.brightness);
      changed();
    });
    els.background.addEventListener('input', () => {
      settings.background = els.background.value;
      els.backgroundValue.textContent = settings.background;
      changed();
    });
    els.smoothing.addEventListener('input', () => {
      settings.smoothing = Number(els.smoothing.value);
      els.smoothingValue.value = settings.smoothing.toFixed(2);
      changed();
    });
    els.showTips.addEventListener('change', () => { settings.show_tips = els.showTips.checked; changed(); });
    els.mirror.addEventListener('change', () => { settings.mirror = els.mirror.checked; changed(); });

    for (const button of document.querySelectorAll('[data-reset]')) {
      button.addEventListener('click', () => {
        for (const key of PANEL_KEYS[button.dataset.reset]) settings[key] = config.defaults[key];
        syncUi();
        changed();
      });
    }

    for (const tool of tools) {
      tool.addEventListener('click', () => {
        openPanel(currentPanel() === tool.dataset.panel ? null : tool.dataset.panel);
      });
    }
    els.view.addEventListener('pointerdown', closePanels);
    els.lock.addEventListener('click', toggleLock);
    els.fullscreen.addEventListener('click', toggleFullscreen);
    els.unhide.addEventListener('click', () => setChromeHidden(false));

    buildWheel();

    window.addEventListener('keydown', (e) => {
      const t = e.target;
      const typing =
        t instanceof HTMLTextAreaElement ||
        (t instanceof HTMLInputElement && (t.type === 'text' || t.type === 'color'));
      if (e.key === 'Escape') {
        if (currentPanel()) closePanels();
        else if (typing) t.blur();
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === 'l') toggleLock();
      else if (key === 'h') setChromeHidden(!document.body.classList.contains('chrome-hidden'));
      else if (key === 'f') toggleFullscreen();
    });
    window.addEventListener('resize', () => { if (currentPanel() === 'colour') paintWheel(); });
  }

  function syncPresets() {
    const cs = config.charsets.find((c) => c.id === settings.charset_id);
    const active = cs && cs.chars === settings.charset ? cs.id : 'custom';
    for (const button of els.presets.children) {
      button.setAttribute('aria-checked', String(button.dataset.preset === active));
    }
  }

  function syncUi() {
    syncPresets();
    els.charset.value = settings.charset;
    els.charsetCount.textContent = String(levels());
    els.invert.checked = settings.invert;
    els.columns.value = String(settings.columns);
    els.columnsValue.value = String(settings.columns);
    els.opacity.value = String(settings.opacity);
    els.opacityValue.value = percent(settings.opacity);
    els.brightness.value = String(settings.brightness);
    els.brightnessValue.value = percent(settings.brightness);
    els.background.value = settings.background;
    els.backgroundValue.textContent = settings.background;
    els.smoothing.value = String(settings.smoothing);
    els.smoothingValue.value = Number(settings.smoothing).toFixed(2);
    els.showTips.checked = settings.show_tips;
    els.mirror.checked = settings.mirror;
    syncWheel();
  }

  // ------------------------------------------------------- colour wheel
  // Angle around the wheel rotates hue (0° at the top, clockwise positive).
  // Distance from the centre is saturation: the centre is greyscale, the
  // thin ring at NATURAL_RADIUS is the video as-is, the rim is twice that.
  function radiusToSaturation(r) {
    const [, max] = config.ranges.saturation;
    if (r <= NATURAL_RADIUS) return r / NATURAL_RADIUS;
    return 1 + ((r - NATURAL_RADIUS) / (1 - NATURAL_RADIUS)) * (max - 1);
  }

  function saturationToRadius(s) {
    const [, max] = config.ranges.saturation;
    if (s <= 1) return s * NATURAL_RADIUS;
    return NATURAL_RADIUS + ((s - 1) / (max - 1)) * (1 - NATURAL_RADIUS);
  }

  function hslToRgb(h, s, l) {
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let rgb;
    if (h < 60) rgb = [c, x, 0];
    else if (h < 120) rgb = [x, c, 0];
    else if (h < 180) rgb = [0, c, x];
    else if (h < 240) rgb = [0, x, c];
    else if (h < 300) rgb = [x, 0, c];
    else rgb = [c, 0, x];
    return rgb.map((v) => Math.round((v + m) * 255));
  }

  function paintWheel() {
    const canvas = els.wheelCanvas;
    const cssSize = canvas.clientWidth;
    if (!cssSize) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const n = Math.round(cssSize * dpr);
    if (canvas.width === n && canvas.dataset.painted) {
      syncWheel();
      return;
    }
    canvas.width = canvas.height = n;
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(n, n);
    const d = img.data;
    const c = n / 2;
    const R = c - 1;
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const dx = x + 0.5 - c;
        const dy = y + 0.5 - c;
        const r = Math.hypot(dx, dy) / R;
        const i = (y * n + x) * 4;
        if (r > 1) continue; // transparent
        const hue = (Math.atan2(dx, -dy) * 180) / Math.PI;
        const sat = Math.min(1, r / NATURAL_RADIUS);
        const boost = Math.max(0, (r - NATURAL_RADIUS) / (1 - NATURAL_RADIUS));
        const [rr, gg, bb] = hslToRgb((hue + 360) % 360, sat, 0.56 - 0.12 * boost);
        d[i] = rr;
        d[i + 1] = gg;
        d[i + 2] = bb;
        d[i + 3] = Math.round(255 * Math.min(1, (1 - r) * R));
      }
    }
    ctx.putImageData(img, 0, 0);
    ctx.beginPath();
    ctx.arc(c, c, R * NATURAL_RADIUS, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
    ctx.lineWidth = dpr;
    ctx.stroke();
    canvas.dataset.painted = '1';
    syncWheel();
  }

  function syncWheel() {
    const size = els.wheel.clientWidth || 160;
    const R = size / 2 - 1;
    const r = saturationToRadius(settings.saturation) * R;
    const a = (settings.hue * Math.PI) / 180;
    els.wheelHandle.style.left = `${size / 2 + Math.sin(a) * r}px`;
    els.wheelHandle.style.top = `${size / 2 - Math.cos(a) * r}px`;
    els.hueValue.textContent = degrees(settings.hue);
    els.saturationValue.textContent = percent(settings.saturation);
  }

  function setWheel(hue, saturation) {
    const [hMin, hMax] = config.ranges.hue;
    const [sMin, sMax] = config.ranges.saturation;
    let h = ((hue + 180) % 360 + 360) % 360 - 180;
    h = Math.min(hMax, Math.max(hMin, Math.round(h)));
    settings.hue = h;
    settings.saturation = Math.min(sMax, Math.max(sMin, Math.round(saturation * 100) / 100));
    syncWheel();
    changed();
  }

  function buildWheel() {
    const wheel = els.wheel;
    let dragging = false;

    const fromPointer = (e) => {
      const rect = wheel.getBoundingClientRect();
      const R = rect.width / 2 - 1;
      const dx = e.clientX - (rect.left + rect.width / 2);
      const dy = e.clientY - (rect.top + rect.height / 2);
      const r = Math.min(1, Math.hypot(dx, dy) / R);
      const hue = r < 0.02 ? settings.hue : (Math.atan2(dx, -dy) * 180) / Math.PI;
      setWheel(hue, radiusToSaturation(r));
    };

    wheel.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      dragging = true;
      wheel.setPointerCapture(e.pointerId);
      wheel.focus({ preventScroll: true });
      fromPointer(e);
      e.preventDefault();
    });
    wheel.addEventListener('pointermove', (e) => { if (dragging) fromPointer(e); });
    const end = () => { dragging = false; };
    wheel.addEventListener('pointerup', end);
    wheel.addEventListener('pointercancel', end);
    wheel.addEventListener('dblclick', () => setWheel(config.defaults.hue, config.defaults.saturation));
    wheel.addEventListener('keydown', (e) => {
      const stepH = e.shiftKey ? 15 : 5;
      const stepS = e.shiftKey ? 0.2 : 0.05;
      if (e.key === 'ArrowLeft') setWheel(settings.hue - stepH, settings.saturation);
      else if (e.key === 'ArrowRight') setWheel(settings.hue + stepH, settings.saturation);
      else if (e.key === 'ArrowUp') setWheel(settings.hue, settings.saturation + stepS);
      else if (e.key === 'ArrowDown') setWheel(settings.hue, settings.saturation - stepS);
      else if (e.key === 'Home') setWheel(config.defaults.hue, config.defaults.saturation);
      else return;
      e.preventDefault();
    });
  }

  // ------------------------------------------------------------- actions
  function toggleLock() {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'lock' }));
  }

  function setLocked(value) {
    locked = value;
    els.lock.setAttribute('aria-pressed', String(locked));
    els.lock.lastElementChild.textContent = locked ? 'Locked' : 'Lock';
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.();
  }

  // -------------------------------------------------------------- status
  function setConn(state, text) {
    els.connDot.className = `dot ${state}`;
    els.connText.textContent = text;
  }

  function showNotice(message) {
    els.notice.textContent = message;
    els.notice.hidden = !message;
  }

  function setHint(text) {
    els.hint.textContent = text;
    els.hint.hidden = !text;
  }

  function showStatus(msg) {
    const info = (msg.handInfo || []).map((h) => `${h.hand[0]} ${h.facing}`).join(' · ');
    els.readoutHands.innerHTML = '';
    els.readoutHands.append(`${msg.hands} ${msg.hands === 1 ? 'hand' : 'hands'}`);
    if (info) {
      const dim = document.createElement('span');
      dim.className = 'dim';
      dim.textContent = `  ${info}`;
      els.readoutHands.append(dim);
    }
    if (msg.grid) {
      els.readoutGrid.textContent = `${msg.grid[0]} × ${msg.grid[1]}${msg.twisted ? ' · twisted' : ''}`;
      els.readoutGrid.hidden = false;
      els.rowsNote.textContent = `Right now: ${msg.grid[0]} × ${msg.grid[1]} cells.`;
    } else {
      els.readoutGrid.hidden = true;
      els.rowsNote.textContent = 'Show both hands to see the grid.';
    }
    els.readoutPerf.textContent = `${lastFps} fps · ${msg.ms} ms`;
    els.readoutPerf.hidden = false;
    setHint(msg.hint);
    if (msg.locked !== locked) setLocked(msg.locked);
  }

  // -------------------------------------------------------------- camera
  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('this browser cannot access the camera');
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: false,
    });
    els.video.srcObject = stream;
    await els.video.play();
    if (els.video.readyState < 2) {
      await new Promise((resolve) => els.video.addEventListener('loadeddata', resolve, { once: true }));
    }
    cameraOk = true;
  }

  /** While the server is not ready, show the local camera so the page is never blank. */
  function localPreview() {
    if (ready || !cameraOk) return;
    const v = els.video;
    if (v.videoWidth) {
      sizeView(v.videoWidth, v.videoHeight);
      viewCtx.save();
      if (settings.mirror) {
        viewCtx.translate(els.view.width, 0);
        viewCtx.scale(-1, 1);
      }
      viewCtx.drawImage(v, 0, 0);
      viewCtx.restore();
    }
    requestAnimationFrame(localPreview);
  }

  function sizeView(w, h) {
    if (els.view.width !== w || els.view.height !== h) {
      els.view.width = w;
      els.view.height = h;
    }
  }

  // ----------------------------------------------------------- streaming
  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${scheme}://${location.host}/ws`);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      reconnectDelay = 1000;
      setConn('warn', 'Starting hand tracking');
    };
    ws.onmessage = (event) => {
      if (typeof event.data === 'string') handleJson(JSON.parse(event.data));
      else showFrame(event.data);
    };
    ws.onclose = () => {
      const wasReady = ready;
      ready = false;
      inFlight = false;
      setConn('bad', wasReady ? 'Reconnecting' : 'Server offline');
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 8000);
      requestAnimationFrame(localPreview);
    };
  }

  function handleJson(msg) {
    switch (msg.type) {
      case 'ready':
        ready = true;
        sendSettings();
        setConn('ok', 'Tracking');
        showNotice('');
        pump();
        break;
      case 'status':
        showStatus(msg);
        inFlight = false;
        pump();
        break;
      case 'lock':
        setLocked(msg.locked);
        break;
      case 'error':
        showNotice(msg.message);
        break;
      default:
        break;
    }
  }

  /** Send the next camera frame if the previous one has been answered. */
  function pump() {
    if (!ready || inFlight || !ws || ws.readyState !== WebSocket.OPEN) return;
    const v = els.video;
    if (!cameraOk || v.readyState < 2 || !v.videoWidth) {
      requestAnimationFrame(pump);
      return;
    }
    inFlight = true;
    capture.width = v.videoWidth;
    capture.height = v.videoHeight;
    capture.getContext('2d').drawImage(v, 0, 0);
    capture.toBlob(
      (blob) => {
        if (!blob || !ws || ws.readyState !== WebSocket.OPEN) {
          inFlight = false;
          return;
        }
        blob.arrayBuffer().then((buffer) => {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(buffer);
          else inFlight = false;
        });
      },
      'image/jpeg',
      JPEG_QUALITY,
    );
  }

  async function showFrame(buffer) {
    let bitmap;
    try {
      bitmap = await createImageBitmap(new Blob([buffer], { type: 'image/jpeg' }));
    } catch {
      return;
    }
    sizeView(bitmap.width, bitmap.height);
    viewCtx.drawImage(bitmap, 0, 0);
    bitmap.close();
    framesShown++;
    const now = performance.now();
    if (now - fpsWindowStart >= 500) {
      lastFps = Math.round((framesShown * 1000) / (now - fpsWindowStart));
      framesShown = 0;
      fpsWindowStart = now;
    }
  }

  // ---------------------------------------------------------------- init
  async function init() {
    try {
      config = await (await fetch('/api/config')).json();
    } catch (err) {
      showNotice('Could not reach the server. Is it running?');
      setConn('bad', 'Server offline');
      throw err;
    }
    const stored = loadSettings();
    settings = { ...config.defaults };
    for (const key of Object.keys(config.defaults)) {
      if (key in stored && typeof stored[key] === typeof config.defaults[key]) settings[key] = stored[key];
    }
    buildUi();
    syncUi();
    try {
      await startCamera();
    } catch (err) {
      showNotice(`Camera unavailable: ${err.message}. Allow camera access and reload.`);
      setConn('bad', 'No camera');
      return;
    }
    requestAnimationFrame(localPreview);
    connect();
  }

  init();
})();
