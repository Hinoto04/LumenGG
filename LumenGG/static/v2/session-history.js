(function () {
    const MAX_ITEMS = 5;
    const PREFIX = "lumengg.recentSessions.";

    function storageKey(kind) {
        return `${PREFIX}${kind || "default"}`;
    }

    function loadItems(kind) {
        try {
            const parsed = JSON.parse(window.localStorage.getItem(storageKey(kind)) || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function saveItems(kind, items) {
        try {
            window.localStorage.setItem(storageKey(kind), JSON.stringify(items.slice(0, MAX_ITEMS)));
        } catch (error) {
            // Ignore storage failures so the page remains usable in private or restricted modes.
        }
    }

    function formatDate(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleString(undefined, {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function recordSession(node) {
        const kind = node.dataset.sessionHistoryKind || "";
        const url = node.dataset.sessionUrl || window.location.href;
        const title = node.dataset.sessionTitle || document.title || url;
        const role = node.dataset.sessionRole || "";
        if (!kind || !url) return;

        const items = loadItems(kind).filter((item) => item && item.url !== url);
        items.unshift({
            url,
            title,
            role,
            updatedAt: new Date().toISOString(),
        });
        saveItems(kind, items);
    }

    function renderHistory(section) {
        const kind = section.dataset.sessionHistoryKind || "";
        const list = section.querySelector("[data-session-history-list]");
        if (!kind || !list) return;

        const items = loadItems(kind).filter((item) => item && item.url && item.title).slice(0, MAX_ITEMS);
        section.hidden = !items.length;
        list.replaceChildren();
        items.forEach((item) => {
            const row = document.createElement("a");
            row.className = "v2-session-history-row";
            row.href = item.url;

            const main = document.createElement("span");
            main.textContent = item.title;
            const meta = document.createElement("small");
            meta.textContent = [item.role, formatDate(item.updatedAt)].filter(Boolean).join(" · ");
            row.append(main, meta);
            list.appendChild(row);
        });
    }

    if (!("localStorage" in window)) return;
    document.querySelectorAll("[data-session-history-record]").forEach(recordSession);
    document.querySelectorAll("[data-session-history][data-session-history-kind]").forEach(renderHistory);
})();
