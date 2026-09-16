/* Krillhub: deterministic, batched SVG level of detail. No network or 3D. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const smooth = (a, b, n) => { const t = clamp((n - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  // Length includes antennae and is measured in CSS pixels, not a global zoom tier.
  const weights = (length) => ({ shape: smooth(7, 16, length), detail: smooth(32, 64, length) });
  const randomSource = () => {
    let seed = 0x4b52494c;
    return () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  const node = (tag, attrs, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
    if (parent) parent.appendChild(el);
    return el;
  };
  const attr = (el, key, value) => { value = String(value); if (el.getAttribute(key) !== value) el.setAttribute(key, value); };
  // The same outline is used for batched silhouettes and their promoted proxies.
  const outline = [[-64,12],[-43,4],[-30,-2],[-13,-10],[15,-12],[40,-5],[48,-2],[36,3],[15,9],[-7,7],[-25,12],[-40,13],[-56,20],[-51,13]];
  const antenna = [[35,-5],[82,-22],[37,-3],[93,-4],[36,-1]];
  const polygon = (points, transform) => points.map(([x, y], i) => `${i ? 'L' : 'M'}${transform(x, y)}`).join('') + 'Z';
  const mini = (transform) => polygon(outline, transform) + polygon(antenna, transform);

  function create(svg, layerById, compact) {
    const random = randomSource();
    const animals = [], patches = [], active = new Map(), pool = [];
    const detailLimit = compact ? 96 : 224;
    const patchCount = compact ? 10 : 12;
    const perPatch = compact ? 320 : 600;
    const specs = [
      { id: 'krill-back', offset: -180, sizes: [.05, .057, .065], color: '#81aaa8', alpha: .42, velocity: 5 },
      { id: 'krill-mid', offset: 0, sizes: [.052, .069, .092], color: '#d9ad9b', alpha: .8, velocity: 8 },
      { id: 'krill-front', offset: 215, sizes: [.09, .12, .15], color: '#e9b7a2', alpha: .92, velocity: 12 }
    ];
    const defs = svg.querySelector('defs');
    if (!svg.querySelector('#krill-simple')) node('path', {
      id: 'krill-simple', d: mini((x, y) => `${x} ${y}`), fill: 'currentColor'
    }, defs);
    for (const spec of specs) {
      const layer = layerById.get(spec.id);
      for (let i = 0; i < patchCount; i++) {
        const root = node('g', { class: 'swarm-patch', 'data-patch': patches.length, 'pointer-events': 'none' }, layer.node);
        const patch = {
          root, layer, spec, members: [], bins: [],
          start: -2100 + (i + .3 + random() * .25) / patchCount * 6200,
          rx: 240 + random() * 190, ry: 55 + random() * 90,
          offset: spec.offset + (random() - .5) * 130,
          velocity: spec.velocity * (.8 + random() * .4), phase: random() * Math.PI * 2,
          x: 0, y: 0, cos: 1, sin: 0, angle: 0, wrapped: false,
          visible: false, loop: null, alpha: 1
        };
        for (let band = 0; band < 3; band++) {
          const group = node('g', { class: 'swarm-batch', 'data-band': band }, root);
          const coarse = node('path', { class: 'swarm-dots', fill: 'none', stroke: spec.color, 'stroke-linecap': 'round' }, group);
          const shape = node('path', { class: 'swarm-shapes', fill: spec.color, stroke: 'none' }, group);
          patch.bins.push({ group, coarse, shape, members: [], scale: spec.sizes[band], dirty: true, length: 0 });
        }
        patch.details = node('g', { class: 'swarm-details', color: spec.color }, root);
        for (let j = 0; j < perPatch; j++) {
          const theta = random() * Math.PI * 2, r = Math.pow(random(), .72);
          const lx = Math.cos(theta) * r * patch.rx;
          const ly = Math.sin(theta) * r * patch.ry + Math.sin(lx / patch.rx * 2.4) * patch.ry * .35;
          const bin = patch.bins[j % 3];
          const angle = (random() - .5) * .32;
          const a = { index: animals.length, patch, layer, bin, scale: bin.scale, lx, ly,
            angle, cos: Math.cos(angle), sin: Math.sin(angle), phase: random() * 6.28,
            x: 0, y: 0, node: null, length: 0 };
          const project = (x, y) => `${(lx + (x * a.cos - y * a.sin) * a.scale).toFixed(2)} ${(ly + (x * a.sin + y * a.cos) * a.scale).toFixed(2)}`;
          a.dot = `M${project(-30, 2)}L${project(42, -3)}`;
          a.shape = mini(project);
          animals.push(a); patch.members.push(a); bin.members.push(a);
        }
        patches.push(patch);
      }
    }
    let elapsed = 0;
    const position = (a) => {
      a.x = a.patch.x + a.lx * a.patch.cos - a.ly * a.patch.sin;
      a.y = a.patch.y + a.lx * a.patch.sin + a.ly * a.patch.cos;
      return a;
    };
    const screenPosition = (a) => {
      position(a);
      return { x: a.x * a.layer.scale + a.layer.tx, y: a.y * a.layer.scale + a.layer.ty };
    };
    function update(time) {
      elapsed = time;
      for (const p of patches) {
        const travel = p.start + time * p.velocity + 2600;
        const loop = Math.floor(travel / 7200);
        p.wrapped = p.loop !== null && p.loop !== loop;
        p.loop = loop;
        p.x = ((travel % 7200) + 7200) % 7200 - 2600;
        const phase = p.x * .0027 + .4;
        p.y = 570 - .12 * p.x + Math.sin(phase) * 145 + p.offset + Math.sin(time * .13 + p.phase) * 12;
        p.angle = Math.atan(-.12 + .39 * Math.cos(phase)) + Math.sin(time * .1 + p.phase) * .035;
        p.cos = Math.cos(p.angle); p.sin = Math.sin(p.angle);
        // Fade at the procedural world's edge rather than blinking at the wrap.
        p.alpha = p.spec.alpha * smooth(0, 300, Math.min(p.x + 2600, 4600 - p.x));
        attr(p.root, 'transform', `translate(${p.x.toFixed(3)} ${p.y.toFixed(3)}) rotate(${(p.angle * 180 / Math.PI).toFixed(3)})`);
        attr(p.root, 'opacity', p.alpha.toFixed(3));
      }
    }
    function release(id, item) {
      item.a.bin.dirty = true;
      item.a.node = null;
      item.node.remove();
      active.delete(id); pool.push(item);
    }
    function promote(a) {
      let item = pool.pop();
      if (!item) {
        const el = node('g', { class: 'krill', 'pointer-events': 'all' });
        node('ellipse', { cx: 5, cy: 0, rx: 65, ry: 25, fill: 'transparent' }, el);
        item = { node: el, dot: node('path', { d: 'M-30 2L42-3', fill: 'none', stroke: 'currentColor', 'stroke-linecap': 'round' }, el), proxy: node('use', { href: '#krill-simple' }, el), art: node('use', { href: '#krill-art' }, el) };
      }
      item.a = a; a.node = item.node;
      item.node.dataset.krillId = a.index;
      item.node.setAttribute('transform', `translate(${a.lx} ${a.ly}) rotate(${a.angle * 180 / Math.PI}) scale(${a.scale})`);
      a.patch.details.appendChild(item.node);
      a.bin.dirty = true; active.set(a.index, item);
      return item;
    }
    let lastTier = 'swarm', lastRender = '';
    const animalLayers = specs.map(spec => layerById.get(spec.id));
    function render(width, height, selected) {
      const key = [width, height, elapsed, selected ? selected.index : -1, ...animalLayers.flatMap(layer => [layer.scale, layer.tx, layer.ty])].join(',');
      if (key === lastRender) return lastTier;
      lastRender = key;
      const eligible = [];
      let visibleCount = 0, weightedLength = 0, pathCount = 0;
      for (const p of patches) {
        const s = p.layer.scale, x = p.x * s + p.layer.tx, y = p.y * s + p.layer.ty;
        const radius = (p.rx + p.ry + 100) * s;
        p.visible = x + radius > -100 && x - radius < width + 100 && y + radius > -100 && y - radius < height + 100;
        attr(p.root, 'display', p.visible ? 'inline' : 'none');
        if (p.visible) pathCount += p.bins.length * 2;
        for (const bin of p.bins) {
          bin.length = 160 * bin.scale * s;
          const mix = weights(bin.length).shape;
          attr(bin.coarse, 'opacity', (1 - mix).toFixed(3));
          attr(bin.coarse, 'display', mix < 1 ? 'inline' : 'none');
          attr(bin.shape, 'display', mix > 0 ? 'inline' : 'none');
          // A bounded stroke preserves subpixel marks without turning them into neon blobs.
          attr(bin.coarse, 'stroke-width', (clamp(bin.length * .095, .45, 1.5) / s).toFixed(4));
          attr(bin.shape, 'opacity', mix.toFixed(3));
          if (!p.visible) continue;
          visibleCount += bin.members.length;
          weightedLength += bin.length * bin.members.length;
          if (bin.length < 22) continue;
          for (const a of bin.members) {
            const existing = active.has(a.index);
            if (bin.length < (existing ? 22 : 28)) continue;
            const point = screenPosition(a);
            const margin = Math.max(80, bin.length);
            if (point.x < -margin || point.x > width + margin || point.y < -margin || point.y > height + margin) continue;
            a.length = bin.length;
            eligible.push(a);
          }
        }
      }
      // Keep existing allocations first: camera motion cannot churn the detail pool.
      eligible.sort((a, b) => Number(active.has(b.index)) - Number(active.has(a.index)) || b.length - a.length || a.index - b.index);
      const wanted = new Map();
      if (selected) { selected.length = 160 * selected.scale * selected.layer.scale; wanted.set(selected.index, selected); }
      for (const a of eligible) {
        if (wanted.size >= detailLimit) break;
        wanted.set(a.index, a);
      }
      for (const [id, item] of active) if (!wanted.has(id)) release(id, item);
      for (const [id, a] of wanted) {
        const item = active.get(id) || promote(a);
        const mix = weights(a.length);
        // Selected micro-particles still have a faithful short-line proxy before zooming in.
        const proxyOpacity = mix.shape * (1 - mix.detail);
        attr(item.dot, 'opacity', ((1 - mix.shape) * (1 - mix.detail)).toFixed(3));
        attr(item.dot, 'stroke-width', (clamp(a.length * .095, .45, 1.5) / (a.layer.scale * a.scale)).toFixed(4));
        attr(item.proxy, 'opacity', proxyOpacity.toFixed(3));
        attr(item.art, 'opacity', mix.detail.toFixed(3));
        if (mix.detail > 0) attr(item.art, 'transform', `scale(1 ${(1 + Math.sin(elapsed * 2.1 + a.phase) * .025).toFixed(3)})`);
        attr(item.art, 'display', mix.detail > 0 ? 'inline' : 'none');
        attr(item.node, 'data-detail', mix.detail.toFixed(3));
      }
      // Rebuild geometry only when membership changes, never on every animation frame.
      // Unpromoted animals remain silhouettes, even when the detail budget is exhausted.
      for (const p of patches) for (const bin of p.bins) {
        if (!bin.dirty) continue;
        const rest = bin.members.filter(a => !active.has(a.index));
        bin.coarse.setAttribute('d', rest.map(a => a.dot).join(''));
        bin.shape.setAttribute('d', rest.map(a => a.shape).join(''));
        bin.dirty = false;
      }
      const length = selected ? selected.length : weightedLength / Math.max(1, visibleCount);
      // Hysteresis keeps the tiny UI label stable near a boundary; geometry stays continuous.
      if (length < 10) lastTier = 'swarm';
      else if (length > 48) lastTier = 'detail';
      else if (length > 13 && length < 42) lastTier = 'shapes';
      attr(svg, 'data-lod', lastTier);
      attr(svg, 'data-population', animals.length);
      attr(svg, 'data-detail-count', active.size);
      attr(svg, 'data-detail-limit', detailLimit);
      attr(svg, 'data-batch-paths', pathCount);
      return lastTier;
    }
    function pick(x, y, maxDistance = 28) {
      let chosen = null, best = maxDistance;
      for (const p of patches) {
        if (!p.visible || p.alpha < .04) continue;
        for (const a of p.members) {
          const point = screenPosition(a), d = Math.hypot(point.x - x, point.y - y);
          if (d < best) { best = d; chosen = a; }
        }
      }
      return chosen;
    }
    function nearest(width, height) {
      let chosen = null, best = Infinity;
      for (const p of patches) {
        if (!p.visible || p.alpha < .04) continue;
        for (const a of p.members) {
          const point = screenPosition(a);
          if (point.x < 35 || point.x > width - 35 || point.y < 110 || point.y > height - 145) continue;
          const d = Math.hypot(point.x - width * .57, point.y - height * .56) / Math.sqrt(a.scale);
          if (d < best) { best = d; chosen = a; }
        }
      }
      // Keyboard focus still has a destination after panning into empty water.
      return chosen || animals.find(a => a.patch.x > 600 && a.patch.x < 1200) || animals[0];
    }
    update(0);
    return { animals, update, render, position, screenPosition, pick, nearest };
  }
  window.KrillSwarm = Object.freeze({ create, weights });
})();
