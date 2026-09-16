/* Krillhub — native SVG, layered 2D parallax, no dependencies or network calls. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const svg = $('scene');
  // The URL selects a complete static language page. No language guessing,
  // redirects, translation API, localStorage or additional runtime bundle.
  const t = (key, params = {}) => {
    const message = $('ocean').getAttribute(`data-i18n-${key}`);
    if (message === null) throw new Error(`Missing interface message: ${key}`);
    return message.replace(/\{(\w+)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match);
  };
  // Keep direct-file previews usable; HTTP language links remain clean URLs.
  if (window.location.protocol === 'file:') {
    document.querySelectorAll('.language-switch a, .brand').forEach((link) => {
      link.href = new URL('index.html', link.href).href;
    });
  }
  const NS = 'http://www.w3.org/2000/svg';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const dialog = $('about-dialog');
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
  const mod = (n, m) => ((n % m) + m) % m;
  const random = (() => {
    let seed = 0x4b52494c;
    return () => {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  })();
  const makeSvg = (tag, attrs, parent) => {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    parent.appendChild(node);
    return node;
  };
  const layers = [...svg.querySelectorAll('[data-depth]')].map((node) => ({
    node, depth: Number(node.dataset.depth), scale: 1, tx: 0, ty: 0
  }));
  const layerById = new Map(layers.map((layer) => [layer.node.id, layer]));
  const animals = [];
  const dust = [];
  const mobile = window.innerWidth <= 650;
  const limits = { minZoom: 0.6, maxZoom: 4, minX: -450, maxX: 2050, minY: -300, maxY: 1300 };
  const camera = { x: 800, y: 500, zoom: 1 };
  const target = { ...camera };
  let width = 1600, height = 1000, baseScale = 1, initialized = false;
  let paused = reducedMotion.matches, speed = 1, elapsed = 0;
  let selected = null, frame = null, lastTime = performance.now(), immersive = false;
  let toastTimer = null, lastZoomText = '';

  // Seeded spacing keeps the first composition stable, while each animal has its own phase.
  const schools = [
    { id: 'krill-back', count: mobile ? 70 : 120, min: .055, max: .12, spread: 245, offset: -40, speed: 8, distant: true },
    { id: 'krill-mid', count: mobile ? 150 : 240, min: .10, max: .29, spread: 145, offset: 20, speed: 14 },
    { id: 'krill-front', count: mobile ? 19 : 28, min: .4, max: .85, spread: 210, offset: 205, speed: 19 }
  ];
  for (const school of schools) {
    const layer = layerById.get(school.id);
    if (school.distant) layer.node.setAttribute('pointer-events', 'none');
    for (let i = 0; i < school.count; i++) {
      const index = animals.length;
      const scale = school.min + random() * (school.max - school.min);
      const node = makeSvg('g', {
        class: school.distant ? 'distant-krill' : 'krill',
        opacity: school.distant ? .18 + random() * .27 : .55 + random() * .42
      }, layer.node);
      if (!school.distant) {
        node.dataset.krillId = String(index);
        makeSvg('ellipse', { cx: 5, cy: 2, rx: 59, ry: 23, fill: 'transparent', 'pointer-events': 'all' }, node);
      }
      makeSvg('use', { href: school.distant ? '#krill-distant' : '#krill-art' }, node);
      animals.push({
        node, layer, index, scale, distant: Boolean(school.distant),
        startX: -780 + (i + random() * .8) / school.count * 3160,
        offset: school.offset + (random() + random() - 1) * school.spread,
        phase: random() * Math.PI * 2, velocity: school.speed * (.75 + random() * .5),
        x: 0, y: 0
      });
    }
  }
  for (const [id, count] of [['dust-back', mobile ? 65 : 130], ['dust-front', mobile ? 20 : 35]]) {
    for (let i = 0; i < count; i++) {
      const node = makeSvg('circle', {
        r: id === 'dust-back' ? .5 + random() * 1.1 : .8 + random() * 1.4,
        fill: random() > .75 ? '#e4d4aa' : '#97c9c5', opacity: .08 + random() * .23
      }, $(id));
      dust.push({ node, x: -1000 + random() * 3600, y: -650 + random() * 2300, phase: random() * 6.28, velocity: 1 + random() * 3 });
    }
  }

  function notify(message) {
    $('toast').textContent = message;
    $('toast').classList.add('visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => $('toast').classList.remove('visible'), 2500);
  }
  function overview() {
    return width / height < .8 ? { x: 1020, y: 320, zoom: 1 } : { x: 800, y: 500, zoom: 1 };
  }
  function clampCamera(value) {
    value.x = clamp(value.x, limits.minX, limits.maxX);
    value.y = clamp(value.y, limits.minY, limits.maxY);
    value.zoom = clamp(value.zoom, limits.minZoom, limits.maxZoom);
  }
  function setCamera(value, immediate = false) {
    Object.assign(target, value);
    clampCamera(target);
    if (immediate || reducedMotion.matches) Object.assign(camera, target);
    renderCamera();
    requestTick();
  }
  function renderCamera() {
    for (const layer of layers) {
      // Only translate and scale flat SVG layers; there is no perspective or 3D projection.
      layer.scale = baseScale * Math.pow(camera.zoom, layer.depth);
      layer.tx = width / 2 - (800 + (camera.x - 800) * layer.depth) * layer.scale;
      layer.ty = height / 2 - (500 + (camera.y - 500) * layer.depth) * layer.scale;
      layer.node.setAttribute('transform', `translate(${layer.tx.toFixed(3)} ${layer.ty.toFixed(3)}) scale(${layer.scale.toFixed(5)})`);
    }
    const zoomText = `${Math.round(camera.zoom * 100)}%`;
    if (lastZoomText !== zoomText) {
      $('zoom-label').textContent = zoomText;
      lastZoomText = zoomText;
    }
    $('zoom-in').disabled = target.zoom >= limits.maxZoom - .001;
    $('zoom-out').disabled = target.zoom <= limits.minZoom + .001;
    svg.dataset.zoom = camera.zoom.toFixed(4);
    svg.dataset.cameraX = camera.x.toFixed(3);
    svg.dataset.cameraY = camera.y.toFixed(3);
    if (selected) {
      const p = screenPosition(selected);
      $('reticle').setAttribute('transform', `translate(${p.x.toFixed(2)} ${p.y.toFixed(2)})`);
    }
  }
  function screenPosition(animal) {
    return { x: animal.x * animal.layer.scale + animal.layer.tx, y: animal.y * animal.layer.scale + animal.layer.ty };
  }
  function worldPoint(x, y) {
    return { x: camera.x + (x - width / 2) / (baseScale * camera.zoom), y: camera.y + (y - height / 2) / (baseScale * camera.zoom) };
  }
  function localPoint(event) {
    const rect = svg.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }
  function explore() { document.body.classList.add('exploring'); }
  function clearSelection() {
    selected = null;
    svg.dataset.mode = 'free';
    $('reticle').setAttribute('visibility', 'hidden');
    $('selection-card').hidden = true;
  }
  function focusAnimal(animal) {
    if (!animal) return;
    selected = animal;
    explore();
    svg.dataset.mode = 'follow';
    const label = t('krill-label', { number: String(animal.index + 1).padStart(3, '0') });
    $('reticle-label').textContent = label;
    $('selection-label').textContent = t('following', { label });
    $('selection-card').hidden = false;
    $('reticle').setAttribute('visibility', 'visible');
    setCamera({
      x: 800 + (animal.x - 800) / animal.layer.depth,
      y: 500 + (animal.y - 500) / animal.layer.depth,
      zoom: animal.scale > .35 ? 2 : 2.8
    });
  }
  function focusNearest() {
    const visible = animals.filter((a) => {
      const p = screenPosition(a);
      return !a.distant && p.x > 35 && p.x < width - 35 && p.y > 100 && p.y < height - 145;
    });
    const score = (a) => {
      const p = screenPosition(a);
      return Math.hypot(p.x - width * .57, p.y - height * .56) / (a.scale > .35 ? 1.45 : 1);
    };
    visible.sort((a, b) => score(a) - score(b));
    if (visible[0]) focusAnimal(visible[0]);
    else {
      // A panned-away viewport still has a useful keyboard-accessible focus destination.
      const candidates = animals.filter((a) => !a.distant && a.x > 500 && a.x < 1250);
      focusAnimal(candidates[0]);
    }
  }
  function resetView() {
    clearSelection();
    svg.dataset.mode = 'overview';
    document.body.classList.remove('exploring');
    setCamera(overview());
  }
  function zoomAt(x, y, factor) {
    const anchor = worldPoint(x, y);
    const zoom = clamp(camera.zoom * factor, limits.minZoom, limits.maxZoom);
    clearSelection();
    explore();
    setCamera({ x: anchor.x - (x - width / 2) / (baseScale * zoom), y: anchor.y - (y - height / 2) / (baseScale * zoom), zoom }, true);
  }
  function updateAnimals() {
    for (const animal of animals) {
      const previousX = animal.x;
      animal.x = mod(animal.startX + elapsed * animal.velocity + 800, 3200) - 800;
      const phase = animal.x * .004 + .4 + Math.sin(elapsed * .055) * .2;
      animal.y = 615 - .145 * animal.x + Math.sin(phase) * 110 + animal.offset + Math.sin(elapsed * 1.1 + animal.phase) * 5;
      const slope = -.145 + .44 * Math.cos(phase);
      const angle = Math.atan2(slope, 1) * 180 / Math.PI + Math.sin(elapsed * 1.8 + animal.phase) * 2;
      const breath = 1 + Math.sin(elapsed * 3.1 + animal.phase) * .035;
      animal.node.setAttribute('transform', `translate(${animal.x.toFixed(2)} ${animal.y.toFixed(2)}) rotate(${angle.toFixed(2)}) scale(${animal.scale.toFixed(3)} ${(animal.scale * breath).toFixed(3)})`);
      // Never sweep the camera across the whole scene when a procedural loop wraps.
      if (selected === animal && Math.abs(animal.x - previousX) > 1600) {
        clearSelection();
        notify(t('lost-krill'));
      }
    }
    for (const particle of dust) {
      particle.node.setAttribute('cx', (particle.x + Math.sin(elapsed * .07 + particle.phase) * 15).toFixed(2));
      particle.node.setAttribute('cy', (mod(particle.y - elapsed * particle.velocity + 650, 2300) - 650).toFixed(2));
    }
    $('rays').setAttribute('transform', `translate(${(Math.sin(elapsed * .09) * 15).toFixed(2)} 0)`);
  }
  function tick(now) {
    frame = null;
    const dt = clamp((now - lastTime) / 1000, 0, .05);
    lastTime = now;
    const moving = !paused && !document.hidden && !dialog.open;
    if (moving) { elapsed += dt * speed; updateAnimals(); }
    if (selected) {
      target.x = 800 + (selected.x - 800) / selected.layer.depth;
      target.y = 500 + (selected.y - 500) / selected.layer.depth;
      clampCamera(target);
    }
    const ease = reducedMotion.matches ? 1 : 1 - Math.exp(-dt * 8);
    for (const key of ['x', 'y', 'zoom']) {
      camera[key] += (target[key] - camera[key]) * ease;
      if (Math.abs(target[key] - camera[key]) < .0001) camera[key] = target[key];
    }
    renderCamera();
    const settling = Math.abs(target.x - camera.x) + Math.abs(target.y - camera.y) + Math.abs(target.zoom - camera.zoom) > .001;
    if (!document.hidden && (moving || settling)) frame = window.requestAnimationFrame(tick);
  }
  function requestTick() {
    if (frame === null && !document.hidden) {
      lastTime = performance.now();
      frame = window.requestAnimationFrame(tick);
    }
  }
  function setPaused(value) {
    paused = value;
    svg.dataset.motion = paused ? 'paused' : 'playing';
    $('pause-button').setAttribute('aria-pressed', String(paused));
    $('pause-button').setAttribute('aria-label', t(paused ? 'play' : 'pause'));
    $('pause-icon').setAttribute('href', paused ? '#icon-play' : '#icon-pause');
    $('motion-label').textContent = t(paused ? 'motion-paused' : 'motion-playing');
    requestTick();
  }
  function resize() {
    const rect = svg.getBoundingClientRect();
    width = Math.max(rect.width, 1);
    height = Math.max(rect.height, 1);
    baseScale = Math.max(width / 1600, height / 1000);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (!initialized || svg.dataset.mode === 'overview') {
      Object.assign(camera, overview());
      Object.assign(target, camera);
    }
    initialized = true;
    renderCamera();
    requestTick();
  }

  // Pointer Events unify mouse, pen and touch. All gesture coordinates are CSS pixels.
  const pointers = new Map();
  let moved = false, pinched = false, hit = null, downPoint = null;
  function cancelGesture() {
    for (const id of pointers.keys()) {
      if (svg.hasPointerCapture(id)) svg.releasePointerCapture(id);
    }
    pointers.clear();
    svg.classList.remove('dragging');
    moved = true;
    hit = null;
  }
  svg.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || pointers.size >= 2) return;
    const point = localPoint(event);
    if (pointers.size === 0) {
      moved = false; pinched = false; downPoint = point;
      hit = event.target.closest('[data-krill-id]');
      svg.focus({ preventScroll: true });
    } else { pinched = true; moved = true; }
    pointers.set(event.pointerId, point);
    svg.setPointerCapture(event.pointerId);
    svg.classList.add('dragging');
    event.preventDefault();
  });
  svg.addEventListener('pointermove', (event) => {
    if (!pointers.has(event.pointerId)) return;
    const previous = pointers.get(event.pointerId);
    const point = localPoint(event);
    if (pointers.size === 2) {
      const before = [...pointers.values()];
      const oldMid = { x: (before[0].x + before[1].x) / 2, y: (before[0].y + before[1].y) / 2 };
      const anchor = worldPoint(oldMid.x, oldMid.y);
      const oldDistance = Math.max(1, Math.hypot(before[0].x - before[1].x, before[0].y - before[1].y));
      pointers.set(event.pointerId, point);
      const after = [...pointers.values()];
      const mid = { x: (after[0].x + after[1].x) / 2, y: (after[0].y + after[1].y) / 2 };
      const distance = Math.max(1, Math.hypot(after[0].x - after[1].x, after[0].y - after[1].y));
      const zoom = clamp(camera.zoom * distance / oldDistance, limits.minZoom, limits.maxZoom);
      clearSelection(); explore();
      setCamera({ x: anchor.x - (mid.x - width / 2) / (baseScale * zoom), y: anchor.y - (mid.y - height / 2) / (baseScale * zoom), zoom }, true);
    } else {
      pointers.set(event.pointerId, point);
      if (!moved && Math.hypot(point.x - downPoint.x, point.y - downPoint.y) > 5) moved = true;
      if (moved) {
        clearSelection(); explore();
        setCamera({ x: camera.x - (point.x - previous.x) / (baseScale * camera.zoom), y: camera.y - (point.y - previous.y) / (baseScale * camera.zoom) }, true);
      }
    }
    event.preventDefault();
  });
  function endPointer(event, cancelled = false) {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (!cancelled && pointers.size === 0 && !moved && !pinched) {
      const point = localPoint(event);
      let animal = hit ? animals[Number(hit.dataset.krillId)] : null;
      if (!animal) {
        let best = 28;
        for (const candidate of animals) {
          if (candidate.distant) continue;
          const p = screenPosition(candidate);
          const distance = Math.hypot(point.x - p.x, point.y - p.y);
          if (distance < best) { best = distance; animal = candidate; }
        }
      }
      if (animal) focusAnimal(animal);
      else clearSelection();
    }
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
    if (pointers.size === 0) { svg.classList.remove('dragging'); hit = null; }
    else { moved = true; downPoint = [...pointers.values()][0]; }
  }
  svg.addEventListener('pointerup', (event) => endPointer(event));
  svg.addEventListener('pointercancel', (event) => endPointer(event, true));
  svg.addEventListener('lostpointercapture', (event) => endPointer(event, true));
  window.addEventListener('blur', cancelGesture);
  svg.addEventListener('wheel', (event) => {
    event.preventDefault();
    const point = localPoint(event);
    const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? height : 1);
    zoomAt(point.x, point.y, Math.exp(-clamp(pixels, -300, 300) * .0018));
  }, { passive: false });
  svg.addEventListener('dblclick', (event) => {
    event.preventDefault();
    const point = localPoint(event);
    const anchor = worldPoint(point.x, point.y);
    clearSelection(); explore();
    setCamera({ x: anchor.x, y: anchor.y, zoom: Math.max(camera.zoom, 2.5) });
  });

  $('zoom-in').addEventListener('click', () => zoomAt(width / 2, height / 2, 1.25));
  $('zoom-out').addEventListener('click', () => zoomAt(width / 2, height / 2, .8));
  $('focus-button').addEventListener('click', focusNearest);
  $('explore-button').addEventListener('click', focusNearest);
  $('reset-button').addEventListener('click', resetView);
  $('unfollow-button').addEventListener('click', clearSelection);
  $('pause-button').addEventListener('click', () => setPaused(!paused));
  $('speed-button').addEventListener('click', () => {
    const speeds = [.5, 1, 2];
    speed = speeds[(speeds.indexOf(speed) + 1) % speeds.length];
    $('speed-button').textContent = `${speed}×`;
    $('speed-button').setAttribute('aria-label', t('speed', { speed }));
  });
  function setImmersive(value) {
    immersive = value;
    document.body.classList.toggle('immersive', value);
    for (const node of document.querySelectorAll('.ui')) node.inert = value;
    $('immersive-button').setAttribute('aria-pressed', String(value));
    $('immersive-button').setAttribute('aria-label', t(value ? 'exit-immersive' : 'enter-immersive'));
    $('exit-immersive').hidden = !value;
    (value ? $('exit-immersive') : $('immersive-button')).focus({ preventScroll: true });
  }
  $('immersive-button').addEventListener('click', () => setImmersive(!immersive));
  $('exit-immersive').addEventListener('click', () => setImmersive(false));
  $('help-button').addEventListener('click', () => { dialog.showModal(); requestTick(); });
  $('close-dialog').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', requestTick);
  dialog.addEventListener('click', (event) => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
  $('fullscreen-button').hidden = !document.fullscreenEnabled;
  $('fullscreen-button').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch { notify(t('fullscreen-unavailable')); }
  });
  document.addEventListener('fullscreenchange', () => {
    const full = Boolean(document.fullscreenElement);
    $('fullscreen-button').setAttribute('aria-pressed', String(full));
    $('fullscreen-button').setAttribute('aria-label', t(full ? 'exit-fullscreen' : 'enter-fullscreen'));
    resize();
  });
  document.addEventListener('keydown', (event) => {
    if (dialog.open || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input, textarea, select, [contenteditable="true"]')) return;
    const key = event.key.toLowerCase();
    if ((event.code === 'Space' || key.startsWith('arrow')) && event.target.closest('button, a')) return;
    let handled = true;
    if (event.code === 'Space') { if (!event.repeat) setPaused(!paused); }
    else if (key === 'f') focusNearest();
    else if (key === '0' || key === 'home') resetView();
    else if (key === '+' || key === '=') zoomAt(width / 2, height / 2, 1.25);
    else if (key === '-' || key === '_') zoomAt(width / 2, height / 2, .8);
    else if (key === 'i' && !event.repeat) setImmersive(!immersive);
    else if (key === 'escape') { clearSelection(); if (immersive) setImmersive(false); }
    else if (['arrowleft', 'arrowright', 'arrowup', 'arrowdown'].includes(key)) {
      clearSelection(); explore();
      const step = (event.shiftKey ? 120 : 55) / (baseScale * camera.zoom);
      setCamera({ x: camera.x + (key === 'arrowleft' ? -step : key === 'arrowright' ? step : 0), y: camera.y + (key === 'arrowup' ? -step : key === 'arrowdown' ? step : 0) }, true);
    } else handled = false;
    if (handled) event.preventDefault();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (frame !== null) window.cancelAnimationFrame(frame);
      frame = null;
      cancelGesture();
    } else requestTick();
  });
  reducedMotion.addEventListener('change', (event) => { if (event.matches) setPaused(true); });
  window.addEventListener('resize', resize);
  svg.dataset.mode = 'overview';
  updateAnimals();
  resize();
  setPaused(paused);
})();
