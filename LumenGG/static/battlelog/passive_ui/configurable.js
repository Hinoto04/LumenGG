const panel = api.root.querySelector("[data-config-passive-panel]");
const options = api.options || {};

function asNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

function getValue(key, fallback = 0) {
    return api.get(key, fallback);
}

function valueForCondition(key, overrideKey, overrideValue) {
    return key === overrideKey ? overrideValue : getValue(key, 0);
}

function isActive(value) {
    return value === true || value === "true" || value === "on" || value === "ON";
}

function safeClassName(value) {
    return String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function createLabel(control) {
    const label = document.createElement("div");
    label.className = "config-passive-label";

    const title = document.createElement("strong");
    title.textContent = control.label || control.key || "패시브";
    label.appendChild(title);

    if (control.description) {
        const description = document.createElement("span");
        description.textContent = control.description;
        label.appendChild(description);
    }
    return label;
}

function createButton(text, onClick, extraClass = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `config-passive-button ${extraClass}`.trim();
    button.textContent = text;
    button.disabled = !api.canControl;
    button.addEventListener("click", onClick);
    return button;
}

function createStatus(text, active) {
    const status = document.createElement("span");
    status.className = `config-passive-status ${active ? "is-active" : "is-inactive"}`;
    status.textContent = text;
    return status;
}

function renderTitle() {
    if (!options.title && !options.description) return;
    const titleBox = document.createElement("div");
    titleBox.className = "config-passive-title";
    if (options.title) {
        const title = document.createElement("strong");
        title.textContent = options.title;
        titleBox.appendChild(title);
    }
    if (options.description) {
        const description = document.createElement("span");
        description.textContent = options.description;
        titleBox.appendChild(description);
    }
    panel.appendChild(titleBox);
}

function renderToggle(control) {
    const value = isActive(getValue(control.key, false));
    const row = document.createElement("div");
    row.className = "config-passive-row";
    row.appendChild(createLabel(control));

    const controls = document.createElement("div");
    controls.className = "config-passive-controls";
    controls.appendChild(createStatus(value ? "ON" : "OFF", value));
    controls.appendChild(createButton(value ? "해제" : "활성화", () => {
        api.set(control.key, !value, control.label);
    }, value ? "is-active" : ""));
    row.appendChild(controls);
    panel.appendChild(row);
}

function counterHighlightClass(control, value) {
    const compareKeys = control.highlightHighestWith || control.compareWith || [];
    if (!compareKeys.length) return "";
    const otherValues = compareKeys
        .filter((key) => key !== control.key)
        .map((key) => asNumber(getValue(key, 0)));
    if (!otherValues.length) return "";
    const highestOther = Math.max(...otherValues);
    if (value > highestOther) return " is-dominant";
    if (value < highestOther) return " is-subdued";
    return "";
}

function conditionMet(condition, overrideKey = null, overrideValue = null) {
    if (!condition) return false;
    if (condition.type === "hpAtMost") {
        return asNumber(api.player.hp) <= asNumber(condition.value);
    }
    if (condition.type === "allEquals") {
        return (condition.keys || []).every((key) => asNumber(valueForCondition(key, overrideKey, overrideValue)) === asNumber(condition.value));
    }
    if (condition.type === "allAtLeast") {
        return (condition.keys || []).every((key) => asNumber(valueForCondition(key, overrideKey, overrideValue)) >= asNumber(condition.value));
    }
    if (condition.type === "counterAtLeast") {
        return asNumber(valueForCondition(condition.key, overrideKey, overrideValue)) >= asNumber(condition.value);
    }
    return false;
}

function applyLatchedStatusUpdates(changedKey, changedValue) {
    let chain = Promise.resolve();
    (options.latchedStatuses || []).forEach((status) => {
        const stored = isActive(getValue(status.key, false));
        const shouldActivate = conditionMet(status.activateWhen, changedKey, changedValue);
        const shouldKeep = conditionMet(status.keepWhile || status.activateWhen, changedKey, changedValue);
        if (shouldActivate && !stored) {
            chain = chain.then(() => api.set(status.key, true, status.label));
        } else if (stored && !shouldKeep) {
            chain = chain.then(() => api.set(status.key, false, status.label));
        }
    });
    return chain;
}

function setCounterValue(control, nextValue, label) {
    return api.set(control.key, nextValue, label || control.label).then(() => {
        return applyLatchedStatusUpdates(control.key, nextValue);
    });
}

function renderCounter(control) {
    const value = Math.max(0, asNumber(getValue(control.key, 0)));
    const max = control.max === undefined || control.max === null ? null : asNumber(control.max);
    const row = document.createElement("div");
    row.className = `config-passive-row config-passive-row-${safeClassName(control.key)}${counterHighlightClass(control, value)}`;
    row.appendChild(createLabel(control));

    const controls = document.createElement("div");
    controls.className = "config-passive-controls";
    const minus = createButton("-", () => setCounterValue(control, Math.max(0, value - 1), control.label));
    minus.disabled = !api.canControl || value <= 0;
    const display = document.createElement("span");
    display.className = "config-passive-value";
    display.textContent = max === null ? `${value}${control.unit || ""}` : `${value}/${max}${control.unit || ""}`;
    const plus = createButton("+", () => {
        const nextValue = max === null ? value + 1 : Math.min(max, value + 1);
        setCounterValue(control, nextValue, control.label);
    });
    plus.disabled = !api.canControl || (max !== null && value >= max);
    controls.append(minus, display, plus);
    if (control.reset) {
        const reset = createButton(control.resetText || "0", () => {
            setCounterValue(control, 0, control.resetLabel || control.label);
        }, "is-danger");
        reset.disabled = !api.canControl || value <= 0;
        controls.appendChild(reset);
    }
    row.appendChild(controls);
    panel.appendChild(row);
}

function renderChoice(control) {
    const value = getValue(control.key, control.default || "");
    const row = document.createElement("div");
    row.className = "config-passive-row";
    row.appendChild(createLabel(control));

    const choices = document.createElement("div");
    choices.className = "config-passive-choice";
    (control.choices || []).forEach((choice) => {
        const choiceValue = typeof choice === "string" ? choice : choice.value;
        const choiceLabel = typeof choice === "string" ? choice : choice.label;
        const active = value === choiceValue;
        const button = createButton(choiceLabel, () => api.set(control.key, choiceValue, control.label), active ? "is-active" : "");
        choices.appendChild(button);
    });
    row.appendChild(choices);
    panel.appendChild(row);
}

function renderStatus(control) {
    const active = conditionMet(control.condition);
    const row = document.createElement("div");
    row.className = "config-passive-badge";
    row.appendChild(createLabel(control));
    row.appendChild(createStatus(active ? (control.activeText || "활성") : (control.inactiveText || "비활성"), active));
    panel.appendChild(row);
}

function renderLatchedStatus(control) {
    const stored = isActive(getValue(control.key, false));
    const active = conditionMet(control.activateWhen) || (stored && conditionMet(control.keepWhile || control.activateWhen));
    const row = document.createElement("div");
    row.className = "config-passive-badge";
    row.appendChild(createLabel(control));
    row.appendChild(createStatus(active ? (control.activeText || "활성") : (control.inactiveText || "비활성"), active));
    panel.appendChild(row);
}

function renderThresholdAction(control) {
    const active = isActive(getValue(control.key, false));
    const ready = conditionMet(control.requires);
    const row = document.createElement("div");
    row.className = "config-passive-row";
    row.appendChild(createLabel(control));

    const controls = document.createElement("div");
    controls.className = "config-passive-controls";
    controls.appendChild(createStatus(active ? "ON" : (ready ? "가능" : "대기"), active || ready));

    const button = createButton(active ? "해제" : "발동", () => {
        if (active) {
            api.set(control.key, false, control.label);
            return;
        }
        if (!ready) return;
        api.set(control.key, true, control.label).then(() => {
            (control.resetKeys || []).forEach((key) => api.set(key, 0, control.resetLabel || key));
        });
    }, active ? "is-active" : "");
    button.disabled = !api.canControl || (!active && !ready);
    controls.appendChild(button);
    row.appendChild(controls);
    panel.appendChild(row);
}

function renderControl(control) {
    if (control.type === "toggle") renderToggle(control);
    else if (control.type === "counter") renderCounter(control);
    else if (control.type === "choice") renderChoice(control);
    else if (control.type === "status") renderStatus(control);
    else if (control.type === "latchedStatus") renderLatchedStatus(control);
    else if (control.type === "thresholdAction") renderThresholdAction(control);
}

(options.controls || []).forEach(renderControl);
(options.badges || []).forEach((badge) => {
    if (badge.type === "latchedStatus") renderLatchedStatus(badge);
    else renderStatus({ ...badge, type: "status" });
});
