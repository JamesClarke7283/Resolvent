'use strict';

const $ = (id) => document.getElementById(id);
const show = (id, visible = true) => $(id).classList.toggle('hidden', !visible);
const state = { operations: [], operation: 'differentiate', mode: 'visual', category: null,
  history: [], worksheetId: null, dirty: false, busy: false, result: null, plot: null };
const symbols = { Algebra: 'ƒ', Calculus: '∫', 'Linear algebra': '▦', 'Discrete maths': '∑',
  Statistics: 'σ', 'Logic & sets': '∪', Geometry: '△', Plotting: '∿' };
const opSymbols = { simplify: '≡', expand: '↔', factor: '⋅', solve: 'ƒ', differentiate: '∂',
  integrate: '∫', limit: 'lim', series: '∑', plot: '∿', determinant: '|A|' };
const presets = {
  integral: { operation: 'integrate', expression: 'x**2', syntax: 'python', variable: 'x', parameters: { bounds: [0, 1] } },
  equation: { operation: 'solve', expression: 'x**2 - 5*x + 6 = 0', syntax: 'python', variable: 'x', parameters: { domain: 'real' } },
  plot: { operation: 'plot', expression: '[sin(x), cos(x)]', syntax: 'python', variable: 'x', parameters: { lower: '-2*pi', upper: '2*pi', samples: 501 } },
};

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function toast(message) {
  $('toast').textContent = message;
  show('toast');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => show('toast', false), 3500);
}
function markDirty() { state.dirty = true; $('save-state').textContent = 'Unsaved changes'; }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: {
    'Content-Type': 'application/json',
    'X-Resolvent-Token': document.querySelector('meta[name="resolvent-token"]').content,
    ...options.headers,
  } });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status}).`);
  return data;
}
function currentOp() { return state.operations.find(op => op.id === state.operation); }
function renderCategories() {
  const categories = [...new Set(state.operations.map(op => op.category))];
  $('categories').replaceChildren();
  for (const category of categories) {
    const button = node('button', 'nav-item');
    button.append(node('span', 'nav-icon', symbols[category] || '◇'), document.createTextNode(category));
    button.title = category;
    button.addEventListener('click', () => {
      state.category = category;
      $('operation-search').value = '';
      show('operation-library');
      renderLibrary();
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      button.classList.add('active');
      $('operation-heading').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    $('categories').append(button);
  }
  $('operation-count').textContent = state.operations.length;
}
function renderQuickOperations() {
  const ids = ['simplify', 'solve', 'differentiate', 'integrate', 'plot'];
  $('quick-operations').replaceChildren();
  for (const id of ids) {
    const op = state.operations.find(o => o.id === id);
    const button = node('button', `quick-operation${state.operation === id ? ' active' : ''}`);
    button.append(node('span', '', opSymbols[id]), document.createTextNode(op.label));
    button.setAttribute('aria-pressed', String(state.operation === id));
    button.addEventListener('click', () => { selectOperation(id); markDirty(); });
    $('quick-operations').append(button);
  }
}
function renderLibrary() {
  const search = $('operation-search').value.toLowerCase();
  const matches = state.operations.filter(op => (!state.category || op.category === state.category)
    && `${op.id} ${op.label} ${op.description} ${op.category}`.toLowerCase().includes(search));
  $('library-results').replaceChildren();
  for (const op of matches) {
    const button = node('button', `library-item${op.id === state.operation ? ' active' : ''}`, op.label);
    button.append(node('span', '', op.category));
    button.title = op.description;
    button.addEventListener('click', () => { selectOperation(op.id); markDirty(); show('operation-library', false); });
    $('library-results').append(button);
  }
  if (!matches.length) $('library-results').append(node('p', 'no-results', 'No operations match. Try a different term.'));
}
function selectOperation(id, values = {}) {
  state.operation = id;
  const op = currentOp();
  if (!op) throw new Error(`Unknown operation: ${id}`);
  $('selected-name').textContent = op.label;
  $('selected-description').textContent = op.description;
  $('selected-symbol').textContent = opSymbols[id] || symbols[op.category] || 'ƒ';
  $('operation-parameters').replaceChildren();
  for (const param of op.parameters) {
    const field = node('div', 'field');
    const label = node('label', '', param.label);
    label.htmlFor = `param-${param.name}`;
    const input = node(param.kind === 'choice' ? 'select' : param.kind === 'json' ? 'textarea' : 'input');
    input.id = `param-${param.name}`;
    input.dataset.param = param.name;
    input.dataset.kind = param.kind;
    input.spellcheck = false;
    if (param.kind === 'choice') {
      for (const choice of param.choices) { const opt = node('option', '', choice); opt.value = choice; input.append(opt); }
    } else if (param.kind === 'number') { input.type = 'number'; input.step = '1'; }
    const value = values[param.name] ?? param.default;
    input.value = typeof value === 'object' ? JSON.stringify(value) : value;
    input.addEventListener('input', markDirty);
    field.append(label, input);
    if (param.help) field.append(node('small', '', param.help));
    $('operation-parameters').append(field);
  }
  renderQuickOperations();
  renderLibrary();
}
function setMode(mode) {
  if (state.mode === mode) return;
  if (state.mode === 'visual') $('code-input').value = $('math-input').value;
  if (mode === 'visual' && state.mode === 'python') {
    toast('Python stays in its own editor. Use LaTeX input to move an expression into Visual mode.');
    return;
  }
  if (state.mode === 'python' && mode === 'latex') {
    toast('Enter LaTeX notation here; Python syntax is not automatically converted.');
  }
  if (mode === 'visual') $('math-input').value = $('code-input').value;
  const previous = state.mode;
  state.mode = mode;
  show('visual-editor', mode === 'visual');
  show('code-input', mode !== 'visual');
  show('math-toolbar', mode === 'visual');
  document.querySelectorAll('[data-mode]').forEach(button => {
    button.classList.toggle('active', button.dataset.mode === mode);
    button.setAttribute('aria-selected', String(button.dataset.mode === mode));
  });
  $('input-type').textContent = mode === 'python' ? 'Python maths syntax' : 'LaTeX notation';
  $('syntax-hint').textContent = mode === 'visual' ? 'Write maths as you think it.'
    : mode === 'python' ? 'Explicit multiplication: 2*x · Powers: x**2 · Equations: Eq(x, 2)'
      : 'LaTeX notation, for example: \\frac{x^2}{2}';
  if (mode === 'python' && previous !== 'python') {
    // Keep the two syntaxes distinct instead of silently treating TeX as Python.
    $('code-input').value = '';
  } else if (mode === 'latex' && previous === 'python') $('code-input').value = $('math-input').value;
  $('code-input').placeholder = mode === 'python' ? 'sin(x) * exp(x)' : '\\frac{x^2}{2}';
}
function applyRequest(request) {
  selectOperation(request.operation, request.parameters || {});
  if (request.syntax === 'python') {
    setMode('python');
    $('code-input').value = request.expression;
  } else {
    // Route through the LaTeX tab so switching from Python is deliberate.
    if (state.mode === 'python') setMode('latex');
    $('code-input').value = request.expression;
    $('math-input').value = request.expression;
    setMode('visual');
  }
  $('variable-input').value = request.variable || 'x';
  $('variables-input').value = (request.variables || []).join(', ');
  $('assumptions-input').value = Object.keys(request.assumptions || {}).length ? JSON.stringify(request.assumptions) : '';
  $('precision-input').value = request.precision || 16;
}
function buildRequest() {
  const expression = state.mode === 'visual' ? $('math-input').value : $('code-input').value;
  if (!expression.trim()) throw new Error('Enter an expression first.');
  const parameters = {};
  document.querySelectorAll('[data-param]').forEach(input => {
    const value = input.value.trim();
    if (!value) return;
    if (input.dataset.kind === 'json') {
      try { parameters[input.dataset.param] = JSON.parse(value); }
      catch { throw new Error(`${input.previousSibling.textContent} must be valid JSON.`); }
    } else if (input.dataset.kind === 'number') parameters[input.dataset.param] = Number(value);
    else parameters[input.dataset.param] = value;
  });
  let assumptions = {};
  try { assumptions = JSON.parse($('assumptions-input').value || '{}'); }
  catch { throw new Error('Assumptions must be valid JSON, such as {"x":{"positive":true}}.'); }
  return { operation: state.operation, expression, syntax: state.mode === 'python' ? 'python' : 'latex',
    variable: $('variable-input').value.trim() || 'x',
    variables: $('variables-input').value.split(/[\s,]+/).filter(Boolean),
    assumptions, parameters, precision: Number($('precision-input').value) };
}
async function calculate(request = null, record = true) {
  if (state.busy) return;
  try { request = request || buildRequest(); }
  catch (error) { displayError(error.message); return; }
  state.busy = true;
  $('compute-button').disabled = true;
  $('compute-label').textContent = 'Calculating…';
  show('error-box', false); show('result-content', false); show('result-empty', false); show('result-loading');
  $('result-status').textContent = 'WORKING';
  $('result-status').className = 'result-status';
  try {
    const result = await api('/api/calculate', { method: 'POST', body: JSON.stringify(request) });
    showResult(result);
    if (record) {
      state.history.unshift({ request: structuredClone(request), result });
      if (state.history.length > 100) state.history.pop();
      renderHistory(); markDirty();
    }
    $('result-heading').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) { displayError(error.message); }
  finally {
    show('result-loading', false);
    state.busy = false;
    $('compute-button').disabled = false;
    $('compute-label').textContent = 'Calculate';
  }
}
function displayError(message) {
  $('error-box').textContent = message;
  show('error-box'); show('result-empty', false); show('result-content', false);
  $('result-status').textContent = 'CHECK INPUT';
  $('result-status').className = 'result-status conditional';
  $('result-heading').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function renderMath(container, latex, fallback) {
  container.replaceChildren();
  try {
    const mf = document.createElement('math-field');
    mf.readOnly = true;
    mf.setAttribute('read-only', '');
    mf.setAttribute('aria-label', fallback);
    mf.tabIndex = -1;
    mf.value = latex;
    container.append(mf);
  } catch { container.textContent = fallback; }
}
function showResult(result) {
  state.result = result;
  show('error-box', false); show('result-empty', false); show('result-content');
  $('result-status').textContent = result.status === 'unevaluated' ? 'CONDITIONAL / UNEVALUATED' : 'COMPUTED';
  $('result-status').className = `result-status ${result.status === 'ok' ? 'complete' : 'conditional'}`;
  renderMath($('result-math'), result.latex, result.result);
  show('numeric-row', Boolean(result.numeric && result.numeric !== result.result));
  $('numeric-result').textContent = result.numeric || '';
  $('result-warnings').replaceChildren(...result.warnings.map(w => node('p', '', w)));
  $('result-timing').textContent = `${result.elapsed_ms < 1000 ? `${Math.round(result.elapsed_ms)} ms` : `${(result.elapsed_ms / 1000).toFixed(2)} s`} · ${result.status === 'ok' ? 'Complete' : 'Partial result'}`;
  $('result-json').textContent = JSON.stringify(result.data, null, 2);
  show('plot-container', Boolean(result.plot));
  state.plot = result.plot;
  if (result.plot) renderPlot(result.plot);
}
function renderHistory() {
  $('history-list').replaceChildren();
  if (!state.history.length) {
    const empty = node('div', 'history-empty');
    empty.append(node('span', '', '↶'), node('p', '', 'Your steps, kept together.\nCalculations appear here.'));
    $('history-list').append(empty); return;
  }
  for (const [index, item] of state.history.entries()) {
    const op = state.operations.find(o => o.id === item.request.operation);
    const button = node('button', 'history-item');
    button.append(node('span', '', opSymbols[op.id] || symbols[op.category]));
    const detail = node('div');
    detail.append(node('strong', '', `${state.history.length - index}. ${op.label}`), node('code', '', item.result?.result || item.request.expression));
    button.append(detail);
    button.title = item.request.expression;
    button.addEventListener('click', () => {
      applyRequest(item.request);
      if (item.result) showResult(item.result);
      else calculate(item.request, false);
    });
    $('history-list').append(button);
  }
}
function worksheetPayload() {
  return { title: $('worksheet-title').value.trim() || 'Untitled worksheet',
    cells: [...state.history].reverse().map(item => item.request) };
}
async function saveWorksheet() {
  if (state.busy) return toast('Wait for the calculation to finish before saving.');
  if (!state.history.length) return toast('Calculate an expression to add a worksheet cell first.');
  $('save-button').disabled = true;
  try {
    const saved = await api(`/api/worksheets${state.worksheetId ? `/${state.worksheetId}` : ''}`, {
      method: state.worksheetId ? 'PUT' : 'POST', body: JSON.stringify(worksheetPayload()),
    });
    state.worksheetId = saved.id; state.dirty = false;
    $('save-state').textContent = 'Saved locally'; toast('Worksheet saved on this device.');
    await refreshSaved();
  } catch (error) { toast(error.message); }
  finally { $('save-button').disabled = false; }
}
async function confirmAction(title, message) {
  $('confirm-title').textContent = title; $('confirm-message').textContent = message;
  const dialog = $('confirm-dialog'); dialog.showModal();
  return new Promise(resolve => {
    let settled = false;
    function finish(answer) {
      if (settled) return; settled = true; dialog.close();
      $('confirm-ok').removeEventListener('click', yes);
      $('confirm-cancel').removeEventListener('click', no);
      dialog.removeEventListener('cancel', cancel); resolve(answer);
    }
    const yes = () => finish(true), no = () => finish(false), cancel = event => { event.preventDefault(); finish(false); };
    $('confirm-ok').addEventListener('click', yes); $('confirm-cancel').addEventListener('click', no); dialog.addEventListener('cancel', cancel);
  });
}
async function canReplaceWorksheet() {
  if (state.busy) { toast('Wait for the current calculation to finish.'); return false; }
  return !state.dirty || await confirmAction('Leave this worksheet?', 'Unsaved changes will be lost. Save your worksheet first if you want to keep them.');
}
async function openWorksheet(data) {
  if (!await canReplaceWorksheet()) return;
  state.worksheetId = data.id || null; state.result = null;
  state.history = data.cells.map(request => ({ request, result: null })).reverse();
  $('worksheet-title').value = data.title;
  state.dirty = !data.id; $('save-state').textContent = data.id ? 'Saved locally' : 'Imported · not saved';
  renderHistory();
  if (data.cells.length) applyRequest(data.cells.at(-1));
  show('result-content', false); show('error-box', false); show('result-empty'); show('saved-panel', false);
  toast('Worksheet opened. Select a history item to recalculate it.');
}
async function refreshSaved() {
  const { worksheets } = await api('/api/worksheets');
  $('saved-count').textContent = worksheets.length;
  $('saved-list').replaceChildren();
  for (const worksheet of worksheets) {
    const entry = node('div', 'saved-entry');
    const open = node('button');
    open.append(node('strong', '', worksheet.title), node('small', '', new Date(worksheet.updated_at).toLocaleString()));
    open.addEventListener('click', async () => {
      try { await openWorksheet(await api(`/api/worksheets/${worksheet.id}`)); }
      catch (error) { toast(error.message); }
    });
    const remove = node('button', 'icon-button', '×');
    remove.setAttribute('aria-label', `Delete ${worksheet.title}`);
    remove.addEventListener('click', async () => {
      if (!await confirmAction('Delete this worksheet?', `“${worksheet.title}” will be deleted from this device.`)) return;
      try {
        await api(`/api/worksheets/${worksheet.id}`, { method: 'DELETE' });
        if (state.worksheetId === worksheet.id) { state.worksheetId = null; markDirty(); }
        await refreshSaved(); toast('Worksheet deleted.');
      } catch (error) { toast(error.message); }
    });
    entry.append(open, remove); $('saved-list').append(entry);
  }
  if (!worksheets.length) $('saved-list').append(node('p', 'no-results', 'No saved worksheets yet. Your next idea can be the first.'));
}
function exportWorksheet() {
  const blob = new Blob([JSON.stringify({ format: 'resolvent-worksheet', version: 1, ...worksheetPayload() }, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob), anchor = node('a');
  anchor.href = url; anchor.download = `${($('worksheet-title').value || 'worksheet').replace(/[^a-z0-9_-]/gi, '_')}.json`;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('Worksheet exported as JSON.');
}
async function importWorksheet(event) {
  const file = event.target.files[0]; event.target.value = '';
  if (!file) return;
  if (file.size > 512000) return toast('Worksheet file is too large (maximum 500 KB).');
  try {
    const data = JSON.parse(await file.text());
    if (data.format !== 'resolvent-worksheet' || data.version !== 1 || typeof data.title !== 'string'
      || data.title.length > 120 || !Array.isArray(data.cells) || data.cells.length > 100
      || data.cells.some(c => !c || typeof c.expression !== 'string' || c.expression.length > 8000 || !state.operations.some(op => op.id === c.operation))) {
      throw new Error('This is not a supported Resolvent worksheet.');
    }
    await openWorksheet({ title: data.title, cells: data.cells });
  } catch (error) { toast(error.message); }
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Copied to clipboard.'); }
  catch {
    const input = node('textarea'); input.value = text; input.style.position = 'fixed'; input.style.opacity = '0';
    document.body.append(input); input.select();
    const success = document.execCommand('copy'); input.remove(); toast(success ? 'Copied to clipboard.' : 'Copy is unavailable in this browser.');
  }
}

// Lightweight local SVG plot renderer: no remote services or JavaScript evaluator.
const palette = ['#236d50', '#b88d4d', '#6e7dac', '#b57079', '#6aa4a1', '#9a89ac'];
function svgNode(tag, attrs, text) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (text !== undefined) el.textContent = text;
  return el;
}
function renderPlot(plot) {
  const svg = $('plot-svg'), w = 760, h = 340, pad = { l: 54, r: 20, t: 25, b: 35 };
  svg.replaceChildren(); $('plot-legend').replaceChildren();
  const all = plot.curves.flatMap(c => c.y.filter(y => y !== null)).sort((a, b) => a - b);
  let ymin = all[Math.floor(all.length * .025)], ymax = all[Math.floor((all.length - 1) * .975)];
  if (ymin === ymax) { ymin -= 1; ymax += 1; }
  const buffer = (ymax - ymin) * .12; ymin -= buffer; ymax += buffer;
  const xmin = plot.lower, xmax = plot.upper;
  const X = x => pad.l + (x - xmin) / (xmax - xmin) * (w - pad.l - pad.r);
  const Y = y => h - pad.b - (y - ymin) / (ymax - ymin) * (h - pad.t - pad.b);
  const defs = svgNode('defs', {}), clip = svgNode('clipPath', { id: 'plot-clip' });
  clip.append(svgNode('rect', { x: pad.l, y: pad.t, width: w-pad.l-pad.r, height: h-pad.t-pad.b })); defs.append(clip); svg.append(defs);
  for (let i = 0; i <= 5; i++) {
    const x = xmin + (xmax-xmin)*i/5, y = ymin + (ymax-ymin)*i/5;
    svg.append(svgNode('line', { x1: X(x), x2: X(x), y1: pad.t, y2: h-pad.b, stroke: '#e8eee2', 'stroke-width': 1 }));
    svg.append(svgNode('line', { x1: pad.l, x2: w-pad.r, y1: Y(y), y2: Y(y), stroke: '#e8eee2', 'stroke-width': 1 }));
    svg.append(svgNode('text', { x: X(x), y: h-12, 'text-anchor': 'middle', fill: '#94a388', 'font-size': 11 }, Number(x.toPrecision(3))));
    svg.append(svgNode('text', { x: pad.l-8, y: Y(y)+4, 'text-anchor': 'end', fill: '#94a388', 'font-size': 11 }, Number(y.toPrecision(3))));
  }
  if (ymin <= 0 && ymax >= 0) svg.append(svgNode('line', { x1: pad.l, x2: w-pad.r, y1: Y(0), y2: Y(0), stroke: '#bbcbb0' }));
  if (xmin <= 0 && xmax >= 0) svg.append(svgNode('line', { x1: X(0), x2: X(0), y1: pad.t, y2: h-pad.b, stroke: '#bbcbb0' }));
  plot.curves.forEach((curve, ci) => {
    let path = '', previous = null;
    curve.y.forEach((y, i) => {
      if (y === null || y < ymin - buffer || y > ymax + buffer) { previous = null; return; }
      const jump = previous !== null && Math.abs(y - previous) > (ymax-ymin)*.65;
      path += `${previous === null || jump ? 'M' : 'L'}${X(plot.x[i]).toFixed(2)},${Y(y).toFixed(2)} `;
      previous = y;
    });
    svg.append(svgNode('path', { d: path, fill: 'none', stroke: palette[ci], 'stroke-width': 2.5, 'clip-path': 'url(#plot-clip)' }));
    const item = node('span', 'legend-item'), dot = node('span', 'legend-dot'); dot.style.background = palette[ci];
    item.append(dot, document.createTextNode(curve.label)); $('plot-legend').append(item);
  });
  const crosshair = svgNode('line', { y1: pad.t, y2: h-pad.b, stroke: '#a4b596', 'stroke-dasharray': '3 4', visibility: 'hidden' });
  svg.append(crosshair);
  svg.onpointermove = event => {
    const rect = svg.getBoundingClientRect(), px = (event.clientX - rect.left) / rect.width * w;
    const ratio = Math.max(0, Math.min(1, (px-pad.l)/(w-pad.l-pad.r)));
    const i = Math.round(ratio*(plot.x.length-1));
    crosshair.setAttribute('x1', X(plot.x[i])); crosshair.setAttribute('x2', X(plot.x[i])); crosshair.setAttribute('visibility', 'visible');
    $('plot-coordinate').textContent = `${plot.variable} = ${plot.x[i].toPrecision(5)}  ·  ${plot.curves.map(c => c.y[i] === null ? 'undefined' : c.y[i].toPrecision(5)).join('  /  ')}`;
  };
  svg.onpointerleave = () => { crosshair.setAttribute('visibility', 'hidden'); };
}
async function zoomPlot(factor) {
  if (!state.plot || state.busy) return;
  const last = [...state.history].find(item => item.result?.id === state.result?.id);
  if (!last) return toast('Recalculate this plot before zooming.');
  const mid = (state.plot.lower + state.plot.upper)/2, range = (state.plot.upper-state.plot.lower)*factor/2;
  const request = structuredClone(last.request);
  request.parameters = { ...request.parameters, lower: String(mid-range), upper: String(mid+range) };
  applyRequest(request); await calculate(request);
}

async function init() {
  try {
    await customElements.whenDefined('math-field');
    MathfieldElement.fontsDirectory = '/static/vendor/fonts';
    MathfieldElement.soundsDirectory = '/static/vendor/sounds';
    $('math-input').mathVirtualKeyboardPolicy = 'manual';
    $('math-input').smartFence = true;
    const { operations } = await api('/api/operations');
    state.operations = operations;
    renderCategories(); selectOperation('differentiate'); await refreshSaved();
    document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { setMode(button.dataset.mode); markDirty(); }));
    $('math-input').addEventListener('input', markDirty);
    for (const id of ['code-input', 'variable-input', 'variables-input', 'assumptions-input', 'precision-input', 'worksheet-title']) $(id).addEventListener('input', markDirty);
    $('compute-button').addEventListener('click', () => calculate());
    $('clear-expression').addEventListener('click', () => { $('math-input').value = ''; $('code-input').value = ''; markDirty(); });
    $('example-button').addEventListener('click', () => { applyRequest(currentOp().example); markDirty(); });
    $('browse-button').addEventListener('click', () => { state.category = null; $('operation-search').value = ''; renderLibrary(); show('operation-library', $('operation-library').classList.contains('hidden')); $('operation-search').focus(); });
    $('operation-search').addEventListener('input', renderLibrary);
    document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => { applyRequest(presets[button.dataset.preset]); markDirty(); $('expression-panel').scrollIntoView({ behavior: 'smooth' }); }));
    document.querySelectorAll('[data-insert]').forEach(button => button.addEventListener('click', () => { $('math-input').executeCommand(['insert', button.dataset.insert.replaceAll('\\\\', '\\')]); $('math-input').focus(); markDirty(); }));
    $('keyboard-button').addEventListener('click', () => { window.mathVirtualKeyboard.visible ? window.mathVirtualKeyboard.hide() : window.mathVirtualKeyboard.show(); $('math-input').focus(); });
    $('copy-result').addEventListener('click', () => state.result && copy(state.result.result));
    $('copy-latex').addEventListener('click', () => state.result && copy(state.result.latex));
    $('reuse-result').addEventListener('click', () => {
      if (!state.result) return;
      if (state.mode === 'python') setMode('latex');
      $('code-input').value = state.result.latex; $('math-input').value = state.result.latex; setMode('visual'); markDirty();
      toast('Result placed in the visual editor.');
    });
    $('clear-history').addEventListener('click', async () => {
      if (state.history.length && await confirmAction('Clear calculation history?', 'All cells will be removed from the current worksheet. Saved versions stay on disk.')) { state.history = []; renderHistory(); markDirty(); }
    });
    $('save-button').addEventListener('click', saveWorksheet);
    $('export-button').addEventListener('click', exportWorksheet);
    $('import-file').addEventListener('change', importWorksheet);
    $('new-worksheet').addEventListener('click', async () => {
      if (!await canReplaceWorksheet()) return;
      state.history = []; state.worksheetId = null; state.result = null; state.dirty = false;
      $('worksheet-title').value = 'Untitled worksheet'; $('save-state').textContent = 'Not saved yet';
      applyRequest({ operation: 'differentiate', expression: 'x^3-3x', syntax: 'latex' });
      renderHistory(); show('result-empty'); show('result-content', false); show('error-box', false);
      $('result-status').textContent = 'READY WHEN YOU ARE'; $('result-status').className = 'result-status';
    });
    $('saved-nav').addEventListener('click', () => { show('saved-panel', $('saved-panel').classList.contains('hidden')); });
    $('close-saved').addEventListener('click', () => show('saved-panel', false));
    $('workspace-nav').addEventListener('click', () => { show('saved-panel', false); show('operation-library', false); document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active')); $('workspace-nav').classList.add('active'); });
    ['help-button', 'about-button'].forEach(id => $(id).addEventListener('click', () => $('help-dialog').showModal()));
    ['close-help', 'guide-done'].forEach(id => $(id).addEventListener('click', () => $('help-dialog').close()));
    $('zoom-in').addEventListener('click', () => zoomPlot(.5)); $('zoom-out').addEventListener('click', () => zoomPlot(2));
    document.addEventListener('keydown', event => {
      if (event.key === 'Enter' && event.shiftKey) { event.preventDefault(); calculate(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); saveWorksheet(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') { event.preventDefault(); $('new-worksheet').click(); }
    });
    $('compute-button').disabled = false;
    window.addEventListener('beforeunload', event => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
  } catch (error) { displayError(`Could not initialize the workbench: ${error.message}`); }
}
init();
