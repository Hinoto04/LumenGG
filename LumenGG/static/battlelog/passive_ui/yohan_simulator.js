const panel = api.root.querySelector("[data-yohan-panel]");
const disasterButton = api.root.querySelector("[data-yohan-disaster-toggle]");
const foresightValue = api.root.querySelector("[data-yohan-foresight-value]");
const FORESIGHT_MAX = 10;
const FORESIGHT_INITIAL = 2;
const labels = {
    foresightCounter: panel ? panel.dataset.labelForesightCounter || "예지 카운터" : "예지 카운터",
    disasterOne: panel ? panel.dataset.labelDisasterOne || "디제스터 원" : "디제스터 원",
};

function canControlPanel() {
    return api.canControl !== false;
}

function asPromise(result) {
    return result && typeof result.then === "function" ? result : Promise.resolve(result);
}

function isActive(value) {
    return value === true || value === "true" || value === "on" || value === "ON";
}

function disasterOneActive() {
    return isActive(api.get("disaster_one", false));
}

function asNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
}

function foresightCount() {
    return Math.max(0, Math.min(FORESIGHT_MAX, asNumber(api.get("foresight_counter", FORESIGHT_INITIAL))));
}

function setBusy(busy) {
    api.root.querySelectorAll("button").forEach((button) => {
        button.disabled = busy || !canControlPanel();
    });
}

function setForesight(value) {
    const nextValue = Math.max(0, Math.min(FORESIGHT_MAX, value));
    setBusy(true);
    asPromise(api.set("foresight_counter", nextValue, labels.foresightCounter))
        .finally(() => {
            setBusy(false);
            render();
        });
}

function render() {
    const foresight = foresightCount();
    if (foresightValue) {
        foresightValue.textContent = `${foresight}/${FORESIGHT_MAX}`;
        foresightValue.classList.toggle("is-disabled", !canControlPanel() || foresight <= 0);
        foresightValue.tabIndex = canControlPanel() && foresight > 0 ? 0 : -1;
        foresightValue.setAttribute("role", "button");
    }
    const active = disasterOneActive();
    if (disasterButton) {
        disasterButton.textContent = active ? "ON" : "OFF";
        disasterButton.classList.toggle("is-active", active);
    }
    api.root.querySelectorAll("button").forEach((button) => {
        button.disabled = !canControlPanel();
    });
    api.root.querySelectorAll("[data-yohan-foresight-delta]").forEach((button) => {
        const delta = asNumber(button.dataset.yohanForesightDelta);
        button.disabled = !canControlPanel() || (delta < 0 && foresight <= 0) || (delta > 0 && foresight >= FORESIGHT_MAX);
    });
}

api.root.querySelectorAll("[data-yohan-foresight-delta]").forEach((button) => {
    button.addEventListener("click", () => {
        setForesight(foresightCount() + asNumber(button.dataset.yohanForesightDelta));
    });
});

if (foresightValue) {
    foresightValue.addEventListener("click", () => {
        if (!canControlPanel() || foresightCount() <= 0) return;
        setForesight(0);
    });
    foresightValue.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        foresightValue.click();
    });
}

if (disasterButton) {
    disasterButton.addEventListener("click", () => {
        setBusy(true);
        asPromise(api.set("disaster_one", !disasterOneActive(), labels.disasterOne))
            .finally(() => {
                setBusy(false);
                render();
            });
    });
}

api.root.querySelectorAll("[data-yohan-declare]").forEach((button) => {
    button.addEventListener("click", () => {
        setBusy(true);
        asPromise(api.simulatorAction("yohan_declare_reveal", {
            declaration: button.dataset.yohanDeclare,
        })).finally(() => {
            setBusy(false);
        });
    });
});

api.root.querySelectorAll("[data-yohan-foresight-reveal]").forEach((button) => {
    button.addEventListener("click", () => {
        setBusy(true);
        asPromise(api.simulatorAction("yohan_foresight_reveal", {})).finally(() => {
            setBusy(false);
        });
    });
});

render();
