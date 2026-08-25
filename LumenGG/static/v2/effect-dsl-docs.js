(function () {
    "use strict";

    const input = document.getElementById("dsl-reference-search");
    const content = document.getElementById("dsl-reference-content");
    const status = document.getElementById("dsl-reference-search-status");
    if (!input || !content) return;

    const entries = Array.from(content.querySelectorAll("[data-dsl-entry]"));
    const sections = Array.from(content.querySelectorAll(".dsl-reference-section"));

    function normalize(value) {
        return String(value || "").normalize("NFKC").toLocaleLowerCase("ko-KR").trim();
    }

    function filterReference() {
        const query = normalize(input.value);
        let visible = 0;
        entries.forEach((entry) => {
            const matches = !query || normalize(entry.textContent).includes(query);
            entry.hidden = !matches;
            if (matches) visible += 1;
        });
        sections.forEach((section) => {
            const sectionEntries = Array.from(section.querySelectorAll("[data-dsl-entry]"));
            section.classList.toggle(
                "dsl-search-empty",
                Boolean(query) && sectionEntries.length > 0 && sectionEntries.every((entry) => entry.hidden),
            );
        });
        if (status) status.textContent = query ? `${visible}개 항목` : `${entries.length}개 항목`;
    }

    input.addEventListener("input", filterReference);
    filterReference();
}());
