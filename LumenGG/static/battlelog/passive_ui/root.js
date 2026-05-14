const panel = api.root.querySelector("[data-root-charge-panel]");
const stateLabel = api.root.querySelector("[data-root-charge-state]");
const toggleButton = api.root.querySelector("[data-root-charge-toggle]");

function isCharged() {
    return api.get("root_charge", false) === true;
}

function render() {
    const charged = isCharged();
    panel.classList.toggle("is-charged", charged);
    stateLabel.textContent = charged ? "ON" : "OFF";
    toggleButton.textContent = charged ? "차지 OFF" : "차지 ON";
    toggleButton.disabled = !api.canControl;
}

toggleButton.addEventListener("click", () => {
    api.set("root_charge", !isCharged(), "차지");
});

render();
