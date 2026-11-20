/* Plan drawing: JSON -> SVG. 1 SVG unit = 1 inch. Handles one room or a whole single-storey house.
 * Format 2: {format:2, wall_in, plot:{length_in,width_in}|null,
 *            rooms:[{id,name,type,x_in,y_in,length_in,width_in}],
 *            openings:[{id,room,type,wall:'N'|'S'|'E'|'W',offset_in,width_in,height_in}]}
 * offset_in runs along the room's inside wall face from its top-left (N/S) or top (E/W) corner.
 * Old format 1 (one room, no "rooms") is converted by normalize().
 */
(function (global) {
  var NS = 'http://www.w3.org/2000/svg';
  var COLORS = { bedroom: '#fff7ed', living: '#fefce8', kitchen: '#ecfdf5', washroom: '#eff6ff', store: '#f5f5f4', room: '#fff7ed' };

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function ftin(inches) {
    var t = Math.round(inches), f = Math.floor(t / 12), i = t - f * 12;
    return f + "'-" + i + '"';
  }
  function normalize(p) {
    if (p.format === 2 && p.rooms) { p.openings = p.openings || []; return p; }
    var t = p.wall_in || 9;
    return { format: 2, wall_in: t, plot: null,
             rooms: [{ id: 'r1', name: 'Room', type: 'room', x_in: t, y_in: t, length_in: p.length_in, width_in: p.width_in }],
             openings: (p.openings || []).map(function (o) { o.room = 'r1'; return o; }) };
  }
  function roomById(plan, id) { for (var i = 0; i < plan.rooms.length; i++) if (plan.rooms[i].id === id) return plan.rooms[i]; return plan.rooms[0]; }
  function wallLen(room, wall) { return (wall === 'N' || wall === 'S') ? room.length_in : room.width_in; }

  function openingRect(plan, o) {
    var r = roomById(plan, o.room), t = plan.wall_in, a = o.offset_in, w = o.width_in;
    switch (o.wall) {
      case 'N': return { x: r.x_in + a, y: r.y_in - t, w: w, h: t };
      case 'S': return { x: r.x_in + a, y: r.y_in + r.width_in, w: w, h: t };
      case 'W': return { x: r.x_in - t, y: r.y_in + a, w: t, h: w };
      default: return { x: r.x_in + r.length_in, y: r.y_in + a, w: t, h: w };
    }
  }

  function drawOpening(g, plan, o, fs) {
    var r = openingRect(plan, o), room = roomById(plan, o.room), a = o.offset_in, w = o.width_in;
    var X = room.x_in, Y = room.y_in, L = room.length_in, W = room.width_in;
    el('rect', { x: r.x, y: r.y, width: r.w, height: r.h, fill: '#fff', stroke: 'none' }, g);
    var horiz = (o.wall === 'N' || o.wall === 'S');
    if (o.type === 'window') {
      for (var k = 0; k < 3; k++) {
        var f = (k + 1) / 4;
        if (horiz) el('line', { x1: r.x, x2: r.x + r.w, y1: r.y + r.h * f, y2: r.y + r.h * f, stroke: '#1d4ed8', 'stroke-width': 1 }, g);
        else el('line', { y1: r.y, y2: r.y + r.h, x1: r.x + r.w * f, x2: r.x + r.w * f, stroke: '#1d4ed8', 'stroke-width': 1 }, g);
      }
      el('rect', { x: r.x, y: r.y, width: r.w, height: r.h, fill: 'none', stroke: '#1d4ed8', 'stroke-width': 1.2 }, g);
    } else {
      var hx, hy, lx, ly, sx, sy, sweep;
      if (o.wall === 'S') { hx = X + a; hy = Y + W; lx = hx; ly = hy - w; sx = hx + w; sy = hy; sweep = 0; }
      else if (o.wall === 'N') { hx = X + a; hy = Y; lx = hx; ly = hy + w; sx = hx + w; sy = hy; sweep = 1; }
      else if (o.wall === 'W') { hx = X; hy = Y + a; lx = hx + w; ly = hy; sx = hx; sy = hy + w; sweep = 0; }
      else { hx = X + L; hy = Y + a; lx = hx - w; ly = hy; sx = hx; sy = hy + w; sweep = 1; }
      el('line', { x1: hx, y1: hy, x2: lx, y2: ly, stroke: '#b45309', 'stroke-width': 2 }, g);
      el('path', { d: 'M' + sx + ' ' + sy + ' A' + w + ' ' + w + ' 0 0 ' + sweep + ' ' + lx + ' ' + ly,
                   fill: 'none', stroke: '#b45309', 'stroke-width': 1, 'stroke-dasharray': '4 3' }, g);
    }
    var cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    var lab = el('text', { x: horiz ? cx : (o.wall === 'W' ? cx + fs * 2.2 : cx - fs * 2.2),
                           y: horiz ? (o.wall === 'N' ? cy + fs * 2.2 : cy - fs * 1.5) : cy + fs * 0.35,
                           'font-size': fs * 0.75, 'text-anchor': 'middle', fill: '#374151' }, g);
    lab.textContent = o.id.toUpperCase() + ' ' + ftin(o.width_in);
  }

  function dim(g, x1, y1, x2, y2, label, fs, vertical) {
    el('line', { x1: x1, y1: y1, x2: x2, y2: y2, stroke: '#111', 'stroke-width': 0.8 }, g);
    var tk = fs * 0.5;
    [[x1, y1], [x2, y2]].forEach(function (p) {
      el('line', { x1: p[0] - tk, y1: p[1] + tk, x2: p[0] + tk, y2: p[1] - tk, stroke: '#111', 'stroke-width': 1.2 }, g);
    });
    if (!label) return;
    var mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    var t = el('text', { x: mx, y: my - fs * 0.35, 'font-size': fs, 'text-anchor': 'middle', fill: '#111' }, g);
    if (vertical) t.setAttribute('transform', 'rotate(-90 ' + mx + ' ' + my + ')');
    t.textContent = label;
  }

  function bbox(plan) {
    var t = plan.wall_in, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    plan.rooms.forEach(function (r) {
      x0 = Math.min(x0, r.x_in - t); y0 = Math.min(y0, r.y_in - t);
      x1 = Math.max(x1, r.x_in + r.length_in + t); y1 = Math.max(y1, r.y_in + r.width_in + t);
    });
    return { x0: x0, y0: y0, x1: x1, y1: y1 };
  }

  function render(svg, plan, opts) {
    opts = opts || {};
    plan = normalize(plan);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var t = plan.wall_in, b = bbox(plan);
    var area = { x0: Math.min(b.x0, 0), y0: Math.min(b.y0, 0), x1: b.x1, y1: b.y1 };
    if (plan.plot) { area.x1 = Math.max(area.x1, plan.plot.length_in); area.y1 = Math.max(area.y1, plan.plot.width_in); }
    var span = Math.max(area.x1 - area.x0, area.y1 - area.y0);
    var fs = Math.max(span / 34, 6), m = fs * 7;
    svg.setAttribute('viewBox', [area.x0 - m, area.y0 - m, area.x1 - area.x0 + 2 * m, area.y1 - area.y0 + 2 * m].join(' '));

    var defs = el('defs', {}, svg);
    var pat = el('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, defs);
    el('rect', { width: 6, height: 6, fill: '#f3d9c0' }, pat);
    el('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: '#b45309', 'stroke-width': 1.5 }, pat);

    if (plan.plot) {
      el('rect', { x: 0, y: 0, width: plan.plot.length_in, height: plan.plot.width_in, fill: '#f0fdf4', stroke: '#16a34a',
                   'stroke-width': 1.5, 'stroke-dasharray': '8 5' }, svg);
      var pl = el('text', { x: plan.plot.length_in / 2, y: plan.plot.width_in - fs * 0.8, 'font-size': fs * 0.9, 'text-anchor': 'middle', fill: '#15803d' }, svg);
      pl.textContent = 'PLOT ' + ftin(plan.plot.length_in) + ' x ' + ftin(plan.plot.width_in) + ' · open area / sehen · FRONT ↓';
    }

    // walls: outer rectangles hatched, then the inside of every room on top
    var wg = el('g', {}, svg);
    plan.rooms.forEach(function (r) {
      el('rect', { x: r.x_in - t, y: r.y_in - t, width: r.length_in + 2 * t, height: r.width_in + 2 * t, fill: 'url(#hatch)', stroke: '#111', 'stroke-width': 1 }, wg);
    });
    var rg = el('g', {}, svg);
    plan.rooms.forEach(function (r, idx) {
      var g = el('g', { class: 'room', 'data-idx': idx }, rg);
      el('rect', { x: r.x_in, y: r.y_in, width: r.length_in, height: r.width_in, fill: COLORS[r.type] || '#fff', stroke: '#111', 'stroke-width': 0.8 }, g);
      // shrink labels so they stay inside small rooms (washrooms, stores)
      var f = Math.min(fs, r.length_in / Math.max(4, r.name.length * 0.62), r.width_in / 3.2);
      var n = el('text', { x: r.x_in + r.length_in / 2, y: r.y_in + r.width_in / 2 - f * 0.2, 'font-size': f, 'text-anchor': 'middle', fill: '#374151', 'font-weight': 600 }, g);
      n.textContent = r.name;
      var s = el('text', { x: r.x_in + r.length_in / 2, y: r.y_in + r.width_in / 2 + f * 1.1, 'font-size': Math.min(fs * 0.8, r.length_in / 9), 'text-anchor': 'middle', fill: '#6b7280' }, g);
      s.textContent = ftin(r.length_in) + ' x ' + ftin(r.width_in);
    });

    var og = el('g', {}, svg);
    plan.openings.forEach(function (o, idx) {
      var gg = el('g', { class: 'opening', 'data-idx': idx }, og);
      drawOpening(gg, plan, o, fs);
      if (opts.editable) {
        var r = openingRect(plan, o);
        el('rect', { x: r.x - 4, y: r.y - 4, width: r.w + 8, height: r.h + 8, fill: 'transparent', stroke: '#2563eb', 'stroke-width': 0.6, 'stroke-dasharray': '3 3' }, gg);
      }
    });

    var dg = el('g', {}, svg);
    dim(dg, b.x0, b.y0 - fs * 2.5, b.x1, b.y0 - fs * 2.5, ftin(b.x1 - b.x0) + ' (outside)', fs);
    dim(dg, b.x1 + fs * 2.5, b.y0, b.x1 + fs * 2.5, b.y1, ftin(b.y1 - b.y0) + ' (outside)', fs, true);
    if (plan.rooms.length === 1) {
      var r0 = plan.rooms[0];
      dim(dg, r0.x_in, b.y0 - fs * 1, r0.x_in + r0.length_in, b.y0 - fs * 1, ftin(r0.length_in) + ' (inside)', fs * 0.85);
    }
    var north = el('text', { x: b.x0, y: b.y0 - fs * 4.5, 'font-size': fs, fill: '#6b7280' }, dg);
    north.textContent = 'N ↑ · walls ' + t + '" brick';

    if (opts.editable) enableDrag(svg, plan, opts);
  }

  // Drag state lives on the <svg>, because children are redrawn on every move.
  function enableDrag(svg, plan, opts) {
    function pt(evt) {
      var p = svg.createSVGPoint(); p.x = evt.clientX; p.y = evt.clientY;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    }
    svg.querySelectorAll('.opening').forEach(function (g) {
      g.addEventListener('pointerdown', function (e) {
        var o = plan.openings[+g.dataset.idx], r = roomById(plan, o.room), p = pt(e);
        var along = (o.wall === 'N' || o.wall === 'S') ? p.x - r.x_in : p.y - r.y_in;
        svg._drag = { kind: 'opening', o: o, grab: along - o.offset_in };
        try { svg.setPointerCapture(e.pointerId); } catch (err) {}
        e.preventDefault(); e.stopPropagation();
      });
    });
    svg.querySelectorAll('.room').forEach(function (g) {
      g.addEventListener('pointerdown', function (e) {
        if (svg._drag) return;
        var r = plan.rooms[+g.dataset.idx], p = pt(e);
        svg._drag = { kind: 'room', r: r, dx: p.x - r.x_in, dy: p.y - r.y_in };
        try { svg.setPointerCapture(e.pointerId); } catch (err) {}
        e.preventDefault();
      });
    });
    svg.onpointermove = function (e) {
      var d = svg._drag;
      if (!d) return;
      var p = pt(e);
      if (d.kind === 'opening') {
        var o = d.o, r = roomById(plan, o.room), along = (o.wall === 'N' || o.wall === 'S') ? p.x - r.x_in : p.y - r.y_in;
        var v = Math.round(Math.min(Math.max(along - d.grab, 0), wallLen(r, o.wall) - o.width_in));
        if (v !== o.offset_in) { o.offset_in = v; render(svg, plan, opts); }
      } else {
        var nx = Math.round((p.x - d.dx) / 3) * 3, ny = Math.round((p.y - d.dy) / 3) * 3;
        var s = snap(plan, d.r, nx, ny);
        if (s.x !== d.r.x_in || s.y !== d.r.y_in) { d.r.x_in = s.x; d.r.y_in = s.y; render(svg, plan, opts); }
      }
    };
    svg.onpointerup = svg.onpointercancel = function () {
      if (svg._drag) { svg._drag = null; if (opts.onChange) opts.onChange(plan); }
    };
  }

  // Snap a dragged room so it shares a wall with a neighbour when it comes close (within 12 in).
  function snap(plan, room, x, y) {
    var t = plan.wall_in, best = { x: x, y: y };
    plan.rooms.forEach(function (o) {
      if (o === room) return;
      var cands = [
        ['x', o.x_in + o.length_in + t], ['x', o.x_in - t - room.length_in], ['x', o.x_in], ['x', o.x_in + o.length_in - room.length_in],
        ['y', o.y_in + o.width_in + t], ['y', o.y_in - t - room.width_in], ['y', o.y_in], ['y', o.y_in + o.width_in - room.width_in]
      ];
      cands.forEach(function (c) {
        if (c[0] === 'x' && Math.abs(x - c[1]) < 12) best.x = c[1];
        if (c[0] === 'y' && Math.abs(y - c[1]) < 12) best.y = c[1];
      });
    });
    if (Math.abs(best.x - t) < 12) best.x = t;
    if (Math.abs(best.y - t) < 12) best.y = t;
    return best;
  }

  global.PlanDrawing = { render: render, ftin: ftin, normalize: normalize, wallLen: wallLen, roomById: roomById };
})(window);
