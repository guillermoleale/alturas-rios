// Reemplazo mínimo del objeto `dash` del dashboard original: carga los JSON de data/,
// calcula los valores derivados y redibuja la página cuando cambian los datos, los filtros o el ancho.
(function () {
  const SOURCES = { estaciones: 'data/estaciones.json', alturas: 'data/alturas.json' };
  const DEFAULTS = { estacion: 34, dias: 'todo', tramo: null };
  const state = {};
  const calcs = {};
  const cache = {};
  const subs = [];
  let params = Object.assign({}, DEFAULTS);

  const q = new URLSearchParams(location.search);
  if (q.has('estacion')) params.estacion = Number(q.get('estacion')) || DEFAULTS.estacion;
  if (q.has('dias')) params.dias = q.get('dias');
  if (q.has('tramo')) params.tramo = q.get('tramo');

  const run = (fn) => { try { fn(); } catch (e) { console.error(e); } };
  let pending = false;
  const notify = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; subs.forEach(run); });
  };

  const load = (id) => {
    if (state[id]) return;
    state[id] = { status: 'loading', data: [] };
    fetch(SOURCES[id], { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then((d) => { state[id] = { status: 'ok', data: Array.isArray(d) ? d : (d.rows || d.data || []) }; })
      .catch((e) => { state[id] = { status: 'error', data: [], message: String(e) }; })
      .finally(() => { Object.keys(cache).forEach((k) => delete cache[k]); notify(); });
  };

  const data = (id) => {
    if (SOURCES[id]) { load(id); return Object.assign({ refreshing: false, meta: [] }, state[id]); }
    if (!calcs[id]) return { status: 'missing', data: [], refreshing: false, meta: [] };
    if (cache[id]) return cache[id];
    const ins = calcs[id].inputs.map(data);
    let res;
    if (ins.some((i) => i.status === 'error')) res = { status: 'error', data: [] };
    else if (ins.some((i) => i.status !== 'ok')) res = { status: 'loading', data: [] };
    else {
      try { res = { status: 'ok', data: calcs[id].fn(...ins.map((i) => i.data)) }; }
      catch (e) { console.error(e); res = { status: 'error', data: [], message: String(e) }; }
    }
    res = Object.assign({ refreshing: false, meta: [] }, res);
    if (res.status !== 'loading') cache[id] = res;
    return res;
  };

  const syncUrl = () => {
    const p = new URLSearchParams();
    Object.keys(params).forEach((k) => { if (params[k] != null && String(params[k]) !== String(DEFAULTS[k])) p.set(k, params[k]); });
    const qs = p.toString();
    try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { /* sin historial */ }
  };

  window.dash = {
    data,
    onData(fn) { subs.push(fn); run(fn); },
    calc(id, def) { calcs[id] = def; },
    loader() {},
    params: () => Object.assign({}, params),
    setParams(p) { Object.assign(params, p); syncUrl(); notify(); },
    resetParams() { params = Object.assign({}, DEFAULTS); syncUrl(); notify(); },
    setLink(name) {
      try { history.replaceState(null, '', location.pathname + location.search + (name ? '#' + name : '')); } catch (e) { /* sin historial */ }
    },
    refresh() {},
    colors: ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'],
  };

  let w = window.innerWidth;
  window.addEventListener('resize', () => { if (window.innerWidth !== w) { w = window.innerWidth; notify(); } });
})();
