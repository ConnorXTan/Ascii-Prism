/*
 * ASCII Prism browser client.
 *
 * The page captures the webcam, sends one JPEG frame at a time to the Python
 * server over a WebSocket, and draws whatever comes back. Only one frame is
 * in flight, so the stream naturally runs at whatever rate the server can
 * process. Settings live in localStorage and are pushed to the server on
 * connect and whenever they change.
 */
(() => {
  'use strict';

  const STORAGE_KEY = 'ascii-prism.settings.v2';
  const JPEG_QUALITY = 0.8;

  const $ = (id) => document.getElementById(id);
  const els = {
    stage: $('stage'),
    video: $('video'),
    view: $('view'),
    hint: $('hint'),
    banner: $('banner'),
    conn: $('status-conn'),
    hands: $('status-hands'),
    handInfo: $('status-hand-info'),
    grid: $('status-grid'),
    fps: $('status-fps'),
    ms: $('status-ms'),
    lock: $('lock'),
    fullscreen: $('fullscreen'),
    togglePanel: $('toggle-panel'),
    panel: $('panel'),
    preset: $('charset-preset'),
    charset: $('charset-input'),
    charsetCount: $('charset-count'),
    invert: $('invert'),
    columns: $('columns'),
    columnsValue: $('columns-value'),
    rowsValue: $('rows-value'),
    colorMode: $('color-mode'),
    inkRow: $('ink-row'),
    ink: $('ink'),
    background: $('background'),
    smoothing: $('smoothing'),
    smoothingValue: $('smoothing-value'),
    showTips: $('show-tips'),
    mirror: $('mirror'),
    reset: $('reset'),
  };

  let config = null;
  let settings = null;
  let ws = null;
  let ready = false;
  let inFlight = false;
  let locked = false;
  let cameraOk = false;
  let reconnectDelay = 1000;
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

  function charsetList() {
    return Array.from(settings.charset || ' ');
  }

  // ------------------------------------------------------------------ ui
  function buildUi() {
    for (const cs of config.charsets) {
      const opt = document.createElement('option');
      opt.value = cs.id;
      opt.textContent = cs.label;
      els.preset.appendChild(opt);
    }
    const custom = document.createElement('option');
    custom.value = 'custom';
    custom.textContent = 'Custom';
    els.preset.appendChild(custom);
    els.columns.min = config.columnsRange[0];
    els.columns.max = config.columnsRange[1];
    els.smoothing.max = config.smoothingRange[1];

    els.preset.addEventListener('change', () => {
      const cs = config.charsets.find((c) => c.id === els.preset.value);
      settings.charset_id = els.preset.value;
      if (cs) {
        settings.charset = cs.chars;
        els.charset.value = cs.chars;
        els.charsetCount.textContent = String(charsetList().length);
      }
      changed();
    });
    els.charset.addEventListener('input', () => {
      settings.charset = els.charset.value || ' ';
      settings.charset_id = 'custom';
      els.preset.value = 'custom';
      els.charsetCount.textContent = String(charsetList().length);
      changed();
    });
    els.invert.addEventListener('change', () => { settings.invert = els.invert.checked; changed(); });
    els.columns.addEventListener('input', () => {
      settings.columns = Number(els.columns.value);
      els.columnsValue.textContent = String(settings.columns);
      changed();
    });
    els.colorMode.addEventListener('change', () => {
      settings.color_mode = els.colorMode.value;
      els.inkRow.hidden = settings.color_mode !== 'mono';
      changed();
    });
    els.ink.addEventListener('input', () => { settings.ink = els.ink.value; changed(); });
    els.background.addEventListener('input', () => { settings.background = els.background.value; changed(); });
    els.smoothing.addEventListener('input', () => {
      settings.smoothing = Number(els.smoothing.value);
      els.smoothingValue.textContent = settings.smoothing.toFixed(2);
      changed();
    });
    els.showTips.addEventListener('change', () => { settings.show_tips = els.showTips.checked; changed(); });
    els.mirror.addEventListener('change', () => { settings.mirror = els.mirror.checked; changed(); });
    els.reset.addEventListener('click', () => {
      settings = { ...config.defaults };
      syncUi();
      changed();
    });
    els.lock.addEventListener('click', toggleLock);
    els.fullscreen.addEventListener('click', () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else els.stage.requestFullscreen?.();
    });
    els.togglePanel.addEventListener('click', () => els.panel.classList.toggle('collapsed'));

    window.addEventListener('keydown', (e) => {
      const t = e.target;
      const typing =
        t instanceof HTMLSelectElement ||
        t instanceof HTMLTextAreaElement ||
        (t instanceof HTMLInputElement && (t.type === 'text' || t.type === 'color'));
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'l' || e.key === 'L') toggleLock();
      if (e.key === 'h' || e.key === 'H') els.panel.classList.toggle('collapsed');
      if (e.key === 'f' || e.key === 'F') els.fullscreen.click();
    });
  }

  function syncUi() {
    const cs = config.charsets.find((c) => c.id === settings.charset_id);
    els.preset.value = cs && cs.chars === settings.charset ? cs.id : 'custom';
    els.charset.value = settings.charset;
    els.charsetCount.textContent = String(charsetList().length);
    els.invert.checked = settings.invert;
    els.columns.value = String(settings.columns);
    els.columnsValue.textContent = String(settings.columns);
    els.colorMode.value = settings.color_mode;
    els.inkRow.hidden = settings.color_mode !== 'mono';
    els.ink.value = settings.ink;
    els.background.value = settings.background;
    els.smoothing.value = String(settings.smoothing);
    els.smoothingValue.textContent = Number(settings.smoothing).toFixed(2);
    els.showTips.checked = settings.show_tips;
    els.mirror.checked = settings.mirror;
  }

  function toggleLock() {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'lock' }));
  }

  function setLocked(value) {
    locked = value;
    els.lock.classList.toggle('active', locked);
    els.lock.textContent = locked ? 'Unlock region' : 'Lock region';
  }

  function setConn(text) {
    els.conn.textContent = text;
  }

  function showBanner(message) {
    els.banner.textContent = message;
    els.banner.hidden = !message;
  }

  function setHint(text) {
    els.hint.textContent = text;
    els.hint.hidden = !text;
  }

  // -------------------------------------------------------------- camera
  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('This browser cannot access the camera (getUserMedia is missing).');
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
      setConn('Starting hand tracking…');
    };
    ws.onmessage = (event) => {
      if (typeof event.data === 'string') handleJson(JSON.parse(event.data));
      else showFrame(event.data);
    };
    ws.onclose = () => {
      const wasReady = ready;
      ready = false;
      inFlight = false;
      setConn(wasReady ? 'Disconnected. Reconnecting…' : 'Server unavailable. Retrying…');
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
        setConn('Tracking');
        showBanner('');
        pump();
        break;
      case 'status':
        els.hands.textContent = String(msg.hands);
        els.handInfo.textContent = (msg.handInfo || [])
          .map((h) => `${h.hand[0]} ${h.facing}`)
          .join(' · ');
        els.grid.textContent = (msg.grid ? `${msg.grid[0]} × ${msg.grid[1]}` : '–') + (msg.twisted ? ' twisted' : '');
        els.rowsValue.textContent = msg.grid ? String(msg.grid[1]) : '–';
        els.ms.textContent = String(msg.ms);
        setHint(msg.hint);
        if (msg.locked !== locked) setLocked(msg.locked);
        inFlight = false;
        pump();
        break;
      case 'lock':
        setLocked(msg.locked);
        break;
      case 'error':
        showBanner(msg.message);
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
      els.fps.textContent = String(Math.round((framesShown * 1000) / (now - fpsWindowStart)));
      framesShown = 0;
      fpsWindowStart = now;
    }
  }

  // ---------------------------------------------------------------- init
  async function init() {
    try {
      config = await (await fetch('/api/config')).json();
    } catch (err) {
      showBanner('Could not reach the server. Is it running?');
      throw err;
    }
    settings = { ...config.defaults, ...loadSettings() };
    buildUi();
    syncUi();
    try {
      await startCamera();
    } catch (err) {
      showBanner(`Camera unavailable: ${err.message}. Allow camera access and reload.`);
      setConn('No camera');
      return;
    }
    requestAnimationFrame(localPreview);
    connect();
  }

  init();
})();
