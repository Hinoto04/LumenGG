(() => {
    const root = document.querySelector("[data-rulebook-search-root]");
    const input = document.querySelector("[data-rulebook-search]");
    const results = document.querySelector("[data-rulebook-search-results]");
    const dataNode = document.getElementById("rulebook-search-data");
    if (!root || !input || !results || !dataNode) return;

    let items = [];
    try {
        items = JSON.parse(dataNode.textContent || "[]");
    } catch (error) {
        items = [];
    }

    function clearResults() {
        root.classList.remove("has-results");
        results.replaceChildren();
    }

    function buildResult(item, query) {
        const link = document.createElement("a");
        link.className = "v2-rulebook-search-result";
        link.href = item.url || `#${item.anchor}`;

        const number = document.createElement("strong");
        number.textContent = item.number || item.anchor || "";

        const text = document.createElement("span");
        const sourceText = item.text || "";
        const index = sourceText.toLocaleLowerCase().indexOf(query);
        text.textContent = index >= 0
            ? `${sourceText.slice(Math.max(0, index - 24), index)}${sourceText.slice(index, index + 120)}`
            : sourceText.slice(0, 140);

        link.append(number, text);
        return link;
    }

    function renderResults() {
        const query = input.value.trim().toLocaleLowerCase();
        if (query.length < 2) {
            clearResults();
            return;
        }

        const terms = query.split(/\s+/).filter(Boolean);
        const matched = items
            .filter((item) => {
                const haystack = `${item.number || ""} ${item.text || ""}`.toLocaleLowerCase();
                return terms.every((term) => haystack.includes(term));
            })
            .slice(0, 30);

        results.replaceChildren();
        if (!matched.length) {
            const empty = document.createElement("p");
            empty.className = "v2-rulebook-search-empty";
            empty.textContent = root.dataset.emptyLabel || "검색 결과가 없습니다.";
            results.appendChild(empty);
            root.classList.add("has-results");
            return;
        }

        matched.forEach((item) => results.appendChild(buildResult(item, query)));
        root.classList.add("has-results");
    }

    input.addEventListener("input", renderResults);
})();

(() => {
    document.querySelectorAll("[data-rule-inline-visual]").forEach((root) => {
        const tabs = Array.from(root.querySelectorAll("[data-rule-inline-visual-tab]"));
        const panels = Array.from(root.querySelectorAll("[data-rule-inline-visual-panel]"));
        if (!tabs.length || !panels.length) return;

        function activate(key) {
            tabs.forEach((tab) => {
                const active = tab.dataset.ruleInlineVisualTab === key;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-selected", active ? "true" : "false");
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.ruleInlineVisualPanel !== key;
            });
        }

        tabs.forEach((tab) => {
            tab.addEventListener("click", () => activate(tab.dataset.ruleInlineVisualTab));
        });
    });
})();
