(() => {
    document.querySelectorAll("[data-rulebook-visual]").forEach((root) => {
        const tabs = Array.from(root.querySelectorAll("[data-rulebook-visual-tab]"));
        const panels = Array.from(root.querySelectorAll("[data-rulebook-visual-panel]"));
        const supportsHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
        const escapeSelectorValue = window.CSS && CSS.escape
            ? CSS.escape
            : (value) => String(value).replace(/["\\]/g, "\\$&");

        function activatePanel(kind) {
            tabs.forEach((tab) => {
                tab.classList.toggle("is-active", tab.dataset.rulebookVisualTab === kind);
            });
            panels.forEach((panel) => {
                const active = panel.dataset.rulebookVisualPanel === kind;
                panel.hidden = !active;
                if (active) {
                    const firstHotspot = panel.querySelector("[data-rulebook-hotspot]");
                    if (firstHotspot) activateHotspot(firstHotspot);
                }
            });
        }

        function setVisualInfo(panel, button) {
            const title = panel.querySelector("[data-rulebook-visual-title]");
            const hint = panel.querySelector("[data-rulebook-visual-hint]");
            const text = panel.querySelector("[data-rulebook-visual-text]");
            const link = panel.querySelector("[data-rulebook-visual-link]");
            if (title) title.textContent = button.dataset.title || "";
            if (hint) {
                hint.textContent = button.dataset.hint || "";
                hint.hidden = !button.dataset.hint;
            }
            if (text) text.textContent = button.dataset.text || "";
            if (link) link.href = button.dataset.href || "#";
        }

        function activateCardMarker(button) {
            const panel = button.closest("[data-rulebook-visual-panel]");
            if (!panel) return;
            panel.querySelectorAll("[data-rulebook-card-marker]").forEach((hotspot) => {
                hotspot.classList.toggle("is-active", hotspot === button);
            });
            setVisualInfo(panel, button);
        }

        function activateCardType(button) {
            const panel = button.closest("[data-rulebook-visual-panel]");
            if (!panel) return;
            const type = button.dataset.rulebookCardType || "";
            panel.querySelectorAll("[data-rulebook-card-type]").forEach((hotspot) => {
                hotspot.classList.toggle("is-active", hotspot === button);
            });

            const image = panel.querySelector("[data-rulebook-card-example-image]");
            if (image && button.dataset.exampleImage) {
                image.src = button.dataset.exampleImage;
            }

            panel.querySelectorAll("[data-rulebook-card-marker-set]").forEach((markerSet) => {
                markerSet.hidden = markerSet.dataset.rulebookCardMarkerSet !== type;
            });

            const firstMarker = panel.querySelector(`[data-rulebook-card-marker-set="${escapeSelectorValue(type)}"] [data-rulebook-card-marker]`);
            if (firstMarker) {
                activateCardMarker(firstMarker);
            } else {
                setVisualInfo(panel, button);
            }
        }

        function activateHotspot(button) {
            const panel = button.closest("[data-rulebook-visual-panel]");
            if (!panel) return;

            if (button.dataset.rulebookCardType) {
                activateCardType(button);
                return;
            }

            if (button.dataset.rulebookCardMarker !== undefined) {
                activateCardMarker(button);
                return;
            }

            panel.querySelectorAll("[data-rulebook-hotspot]").forEach((hotspot) => {
                hotspot.classList.toggle("is-active", hotspot === button);
            });
            setVisualInfo(panel, button);
        }

        function followHotspotLink(button) {
            const href = button.dataset.href || "";
            if (!href || href === "#") return;
            window.location.assign(href);
        }

        tabs.forEach((tab) => {
            tab.addEventListener("click", () => activatePanel(tab.dataset.rulebookVisualTab));
        });
        root.querySelectorAll("[data-rulebook-hotspot]").forEach((button) => {
            button.addEventListener("click", () => {
                const wasActive = button.classList.contains("is-active");
                activateHotspot(button);
                if (wasActive && supportsHover) followHotspotLink(button);
            });
            button.addEventListener("mouseenter", () => activateHotspot(button));
            button.addEventListener("focus", () => activateHotspot(button));
        });

        const activeTab = tabs.find((tab) => tab.classList.contains("is-active")) || tabs[0];
        if (activeTab) activatePanel(activeTab.dataset.rulebookVisualTab);
    });
})();
