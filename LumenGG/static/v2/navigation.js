(() => {
    document.addEventListener("DOMContentLoaded", () => {
        const header = document.querySelector("[data-v2-header]");
        const toggle = header?.querySelector("[data-v2-menu-toggle]");
        const menu = header?.querySelector("[data-v2-header-menu]");
        if (!header || !toggle || !menu) return;

        function setOpen(open) {
            menu.classList.toggle("is-open", open);
            toggle.setAttribute("aria-expanded", String(open));
            const label = open ? toggle.dataset.labelClose : toggle.dataset.labelOpen;
            if (label) {
                toggle.setAttribute("aria-label", label);
                toggle.title = label;
            }
        }

        toggle.addEventListener("click", () => {
            setOpen(toggle.getAttribute("aria-expanded") !== "true");
        });

        menu.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", () => setOpen(false));
        });

        document.addEventListener("click", (event) => {
            if (toggle.getAttribute("aria-expanded") === "true" && !header.contains(event.target)) {
                setOpen(false);
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
                setOpen(false);
                toggle.focus();
            }
        });

        const desktopQuery = window.matchMedia("(min-width: 981px)");
        const handleDesktopChange = (event) => {
            if (event.matches) setOpen(false);
        };
        if (desktopQuery.addEventListener) {
            desktopQuery.addEventListener("change", handleDesktopChange);
        } else {
            desktopQuery.addListener(handleDesktopChange);
        }
    });
})();
