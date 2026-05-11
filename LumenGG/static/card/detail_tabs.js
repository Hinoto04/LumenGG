document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-card-detail-toggle]").forEach((toggle) => {
        const section = toggle.closest("section, #섹션2");
        if (!section) return;

        const panel = section.querySelector("[data-card-detail-panel]");
        if (!panel) return;

        toggle.addEventListener("click", () => {
            const shouldOpen = panel.hidden;
            panel.hidden = !shouldOpen;
            toggle.classList.toggle("is-active", shouldOpen);
            toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            toggle.textContent = shouldOpen ? "-상세 정보" : "+상세 정보";
        });
    });
});
