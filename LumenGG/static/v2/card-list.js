document.querySelectorAll(".dynamicLink").forEach((element) => {
    element.addEventListener("click", function(event) {
        event.preventDefault();
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set("page", this.getAttribute("data-page"));
        window.location.href = currentUrl.toString();
    });
});

const filterToggle = document.getElementById("v2FilterToggle");
const filterGrid = document.getElementById("v2FilterGrid");

if (filterToggle && filterGrid) {
    const params = new URLSearchParams(window.location.search);
    const hasFilter = [...params.keys()].some((key) => key !== "page" && key !== "keyword" && key !== "sort");
    if (hasFilter) {
        filterGrid.classList.add("is-open");
    }

    filterToggle.addEventListener("click", () => {
        filterGrid.classList.toggle("is-open");
    });
}

document.querySelectorAll(".v2-clickable-card[data-href]").forEach((card) => {
    const openCard = () => {
        window.location.href = card.dataset.href;
    };

    card.addEventListener("click", (event) => {
        if (event.target.closest("a, button, input, select, textarea, label")) return;
        openCard();
    });

    card.addEventListener("keydown", (event) => {
        if (event.target !== card) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openCard();
    });
});
