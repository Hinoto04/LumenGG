(function () {
    const storageKey = "lumendb-theme";
    const validThemes = new Set(["dark", "light"]);

    function getStoredTheme() {
        try {
            const theme = window.localStorage.getItem(storageKey);
            return validThemes.has(theme) ? theme : "";
        } catch (error) {
            return "";
        }
    }

    function getDefaultTheme() {
        const bodyDefault = document.body ? document.body.dataset.defaultTheme : "";
        const htmlDefault = document.documentElement.dataset.defaultTheme || "";
        return validThemes.has(bodyDefault) ? bodyDefault : (validThemes.has(htmlDefault) ? htmlDefault : "dark");
    }

    function getCurrentTheme() {
        const htmlTheme = document.documentElement.dataset.theme;
        return validThemes.has(htmlTheme) ? htmlTheme : (getStoredTheme() || getDefaultTheme());
    }

    function setMetaThemeColor(theme) {
        const meta = document.querySelector('meta[name="theme-color"]');
        if (!meta) return;
        meta.setAttribute("content", theme === "light" ? "#f4efe4" : "#111111");
    }

    function updateToggleButtons(theme) {
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            const nextTheme = theme === "light" ? "dark" : "light";
            const label = button.querySelector("[data-theme-toggle-label]") || button;
            label.textContent = nextTheme === "light" ? "라이트" : "다크";
            button.setAttribute("aria-label", `${label.textContent} 테마로 변경`);
            button.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
            button.title = `${label.textContent} 테마로 변경`;
        });
    }

    function applyTheme(theme, persist) {
        const nextTheme = validThemes.has(theme) ? theme : getDefaultTheme();
        document.documentElement.dataset.theme = nextTheme;
        document.documentElement.style.colorScheme = nextTheme;
        setMetaThemeColor(nextTheme);
        updateToggleButtons(nextTheme);

        if (persist) {
            try {
                window.localStorage.setItem(storageKey, nextTheme);
            } catch (error) {
                // 테마 저장 실패는 화면 동작을 막을 필요가 없습니다.
            }
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        applyTheme(getCurrentTheme(), false);
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const currentTheme = getCurrentTheme();
                applyTheme(currentTheme === "light" ? "dark" : "light", true);
            });
        });
    });
})();
