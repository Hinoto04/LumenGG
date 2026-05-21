const panel = api.root.querySelector("[data-tao-panel]");
const harmonyRow = api.root.querySelector("[data-tao-harmony-row]");
const labels = {
    yang: panel ? panel.dataset.labelYang || "양" : "양",
    yin: panel ? panel.dataset.labelYin || "음" : "음",
    harmony: panel ? panel.dataset.labelHarmony || "조화" : "조화",
    harmonyEffect: panel ? panel.dataset.labelHarmonyEffect || "조화 효과" : "조화 효과",
};

function canControlPanel() {
    return api.canControl !== false;
}

function asPromise(result) {
    return result && typeof result.then === "function" ? result : Promise.resolve(result);
}

function asNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
}

function isActive(value) {
    return value === true || value === "true" || value === "on" || value === "ON";
}

function getYang() {
    return Math.max(0, Math.min(4, asNumber(api.get("yang_counter", 0))));
}

function getYin() {
    return Math.max(0, Math.min(4, asNumber(api.get("yin_counter", 0))));
}

function isHarmony() {
    return isActive(api.get("harmony", false));
}

function selectedEffect() {
    return String(api.get("harmony_effect", "") || "");
}

function shouldActivateHarmony(yang, yin) {
    return yang === 4 && yin === 4;
}

function shouldKeepHarmony(yang, yin) {
    return yang >= 3 && yin >= 3;
}

function setBusy(busy) {
    api.root.querySelectorAll("button").forEach((button) => {
        button.disabled = busy || !canControlPanel();
    });
}

function syncHarmonyAfterCounterChange(yang, yin) {
    const harmonyStored = isHarmony();
    if (shouldActivateHarmony(yang, yin) && !harmonyStored) {
        return asPromise(api.set("harmony", true, labels.harmony));
    }
    if (harmonyStored && !shouldKeepHarmony(yang, yin)) {
        return asPromise(api.set("harmony_effect", "", labels.harmonyEffect))
            .then(() => asPromise(api.set("harmony", false, labels.harmony)));
    }
    return Promise.resolve();
}

function setCounter(counter, value) {
    const key = counter === "yang" ? "yang_counter" : "yin_counter";
    const label = counter === "yang" ? labels.yang : labels.yin;
    const nextValue = Math.max(0, Math.min(4, value));
    const nextYang = counter === "yang" ? nextValue : getYang();
    const nextYin = counter === "yin" ? nextValue : getYin();

    setBusy(true);
    asPromise(api.set(key, nextValue, label))
        .then(() => syncHarmonyAfterCounterChange(nextYang, nextYin))
        .finally(() => setBusy(false));
}

function setHarmonyEffect(effect) {
    const harmonyStored = isHarmony();
    const canActivate = shouldActivateHarmony(getYang(), getYin());
    if (!harmonyStored && !canActivate) return;
    setBusy(true);
    const chain = harmonyStored
        ? Promise.resolve()
        : asPromise(api.set("harmony", true, labels.harmony));
    chain
        .then(() => asPromise(api.set("harmony_effect", effect, labels.harmonyEffect)))
        .finally(() => setBusy(false));
}

function render() {
    if (!panel) return;
    const yang = getYang();
    const yin = getYin();
    const harmony = isHarmony() || shouldActivateHarmony(yang, yin);
    const effect = selectedEffect();

    panel.classList.toggle("is-harmony", harmony);
    const yangValue = panel.querySelector("[data-tao-value='yang']");
    const yinValue = panel.querySelector("[data-tao-value='yin']");
    yangValue.textContent = `${yang}/4`;
    yinValue.textContent = `${yin}/4`;
    yangValue.setAttribute("role", "button");
    yinValue.setAttribute("role", "button");
    yangValue.tabIndex = canControlPanel() && yang > 0 ? 0 : -1;
    yinValue.tabIndex = canControlPanel() && yin > 0 ? 0 : -1;
    yangValue.classList.toggle("is-disabled", !canControlPanel() || yang <= 0);
    yinValue.classList.toggle("is-disabled", !canControlPanel() || yin <= 0);

    const yangCard = panel.querySelector("[data-tao-card='yang']");
    const yinCard = panel.querySelector("[data-tao-card='yin']");
    yangCard.classList.toggle("is-dominant", !harmony && yang > yin);
    yinCard.classList.toggle("is-dominant", !harmony && yin > yang);
    yangCard.classList.toggle("is-harmony", harmony);
    yinCard.classList.toggle("is-harmony", harmony);

    harmonyRow.hidden = !harmony;
    harmonyRow.querySelectorAll("[data-tao-effect]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.taoEffect === effect);
        button.disabled = !canControlPanel() || !harmony;
    });

    panel.querySelectorAll("[data-tao-counter]").forEach((button) => {
        const counter = button.dataset.taoCounter;
        const current = counter === "yang" ? yang : yin;
        const delta = asNumber(button.dataset.taoDelta);
        const isReset = button.hasAttribute("data-tao-reset");
        button.disabled = (
            !canControlPanel()
            || (isReset && current <= 0)
            || (delta < 0 && current <= 0)
            || (delta > 0 && current >= 4)
        );
    });
}

api.root.querySelectorAll("[data-tao-delta]").forEach((button) => {
    button.addEventListener("click", () => {
        const counter = button.dataset.taoCounter;
        const current = counter === "yang" ? getYang() : getYin();
        setCounter(counter, current + asNumber(button.dataset.taoDelta));
    });
});

api.root.querySelectorAll("[data-tao-reset]").forEach((button) => {
    button.addEventListener("click", () => {
        setCounter(button.dataset.taoCounter, 0);
    });
});

api.root.querySelectorAll("[data-tao-value]").forEach((valueNode) => {
    valueNode.addEventListener("click", () => {
        const counter = valueNode.dataset.taoValue;
        const current = counter === "yang" ? getYang() : getYin();
        if (!canControlPanel() || current <= 0) return;
        setCounter(counter, 0);
    });
    valueNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        valueNode.click();
    });
});

api.root.querySelectorAll("[data-tao-effect]").forEach((button) => {
    button.addEventListener("click", () => {
        setHarmonyEffect(button.dataset.taoEffect);
    });
});

render();
