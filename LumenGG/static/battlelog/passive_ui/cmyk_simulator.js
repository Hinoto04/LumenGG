const button = api.root.querySelector("[data-cmyk-new-single]");
let locallyCreated = false;

function canControlPanel() {
    return api.canControl !== false;
}

function asPromise(result) {
    return result && typeof result.then === "function" ? result : Promise.resolve(result);
}

function isActive(value) {
    return value === true || value === "true" || value === "on" || value === "ON";
}

function created() {
    return locallyCreated || isActive(api.get("new_single_created", false));
}

function render() {
    if (!button) return;
    const done = created();
    button.disabled = !canControlPanel() || done;
    button.classList.toggle("is-active", done);
    button.textContent = done ? "생성됨" : "10장 생성";
}

if (button) {
    button.addEventListener("click", () => {
        if (!canControlPanel() || created()) return;
        button.disabled = true;
        asPromise(api.simulatorAction("cmyk_new_single", {}))
            .then((result) => {
                if (result) locallyCreated = true;
            })
            .finally(render);
    });
}

render();
