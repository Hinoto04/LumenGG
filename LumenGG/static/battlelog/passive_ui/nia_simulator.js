const button = api.root.querySelector("[data-nia-lumen-to-list]");

function canControlPanel() {
    return api.canControl !== false;
}

function asPromise(result) {
    return result && typeof result.then === "function" ? result : Promise.resolve(result);
}

if (button) {
    button.disabled = !canControlPanel();
    button.addEventListener("click", () => {
        if (!canControlPanel()) return;
        button.disabled = true;
        asPromise(api.simulatorAction("nia_lumen_cards_to_list", {}))
            .finally(() => {
                button.disabled = !canControlPanel();
            });
    });
}
