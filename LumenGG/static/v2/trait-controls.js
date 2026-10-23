window.renderTraitControls = function(api) {
  const definition = api.player.character?.passive_ui?.options || {};
  const model = window.CalculatorTraitModel;
  api.root.replaceChildren();
  const panel = document.createElement('div'); panel.className = 'v2-trait-controls';
  panel.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;max-height:240px;overflow:auto';
  const send = (control, value) => api.dispatch(model.passiveActions(api.player, definition, api.target, control.key, value, control.label || control.key));
  for (const control of [...(definition.controls || []), ...(definition.badges || []).map(c => ({...c, type:c.type || 'status'}))]) {
    if (control.visibleWhen && !model.conditionMet(control.visibleWhen, api.player)) continue;
    const label = document.createElement('label'); label.textContent = control.label || control.key;
    const current = api.get(control.key, control.default ?? control.initial ?? 0);
    let input;
    if (['status','latchedStatus'].includes(control.type)) { const value = document.createElement('span'); value.textContent = String(control.condition ? model.conditionMet(control.condition, api.player) : !!current); label.append(value); panel.append(label); continue; }
    if (control.type === 'choice') {
      input = document.createElement('select'); for (const choice of control.choices || []) { const o = document.createElement('option'); o.value = choice.value; o.textContent = choice.label; input.append(o); }
      input.value = current; input.addEventListener('change', () => send(control, input.value));
    } else {
      input = document.createElement('input'); input.type = ['toggle','thresholdAction'].includes(control.type) ? 'checkbox' : control.type === 'counter' ? 'number' : 'text';
      if (input.type === 'checkbox') input.checked = !!current; else input.value = current;
      if (input.type === 'number') { input.min = control.min ?? 0; if (control.max != null) input.max = control.max; input.style.width = '72px'; }
      input.addEventListener('change', () => send(control, input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value));
    }
    input.disabled = !api.canControl || !!(control.enableWhen && !model.conditionMet(control.enableWhen, api.player));
    label.append(input); panel.append(label);
  }
  api.root.append(panel);
};
