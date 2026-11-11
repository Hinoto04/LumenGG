const changedCollection = {};
const changedCategories = {};
const collectionConfig = window.v2CollectionConfig || {};
const collectionTranslations = collectionConfig.translations || {};

function collectionText(key, fallback) {
    return collectionTranslations[key] || fallback;
}

function setCollectionValue(id, value) {
    const input = document.getElementById(`cc_input_${id}`);
    if (!input) return;

    const nextValue = Math.max(0, Math.min(99, Number(value) || 0));
    input.value = nextValue;
    changedCollection[id] = nextValue;
}

function inc(id) {
    const input = document.getElementById(`cc_input_${id}`);
    if (!input) return;
    setCollectionValue(id, (Number(input.value) || 0) + 1);
}

function dec(id) {
    const input = document.getElementById(`cc_input_${id}`);
    if (!input) return;
    setCollectionValue(id, (Number(input.value) || 0) - 1);
}

document.querySelectorAll(".cc_input").forEach((input) => {
    input.addEventListener("change", () => {
        setCollectionValue(input.name, input.value);
    });
});

// 분류(하트): 인쇄본마다 0(없음)~5를 고르고, 카드 이미지 왼쪽 위에 같은 묶음의 하트를 모아 보여준다.
function renderCollectionHearts(row) {
    const holder = row.querySelector("[data-collection-hearts]");
    if (!holder) return;
    const categories = [...new Set(
        [...row.querySelectorAll("[data-print-id]")]
            .map((print) => Number(print.dataset.category) || 0)
            .filter((value) => value > 0),
    )].sort((a, b) => a - b);
    holder.replaceChildren(...categories.map((value) => {
        const heart = document.createElement("span");
        heart.className = `v2-heart v2-heart-${value}`;
        heart.textContent = "♥";
        return heart;
    }));
}

function closeCategoryMenus(except) {
    document.querySelectorAll("[data-category-menu]").forEach((menu) => {
        if (menu === except) return;
        menu.hidden = true;
        menu.parentElement.querySelector("[data-category-button]")?.setAttribute("aria-expanded", "false");
    });
}

function setCollectionCategory(print, value) {
    const category = Math.max(0, Math.min(5, Number(value) || 0));
    print.dataset.category = String(category);
    changedCategories[print.dataset.printId] = category;
    const icon = print.querySelector("[data-category-button] .v2-heart");
    if (icon) {
        icon.className = `v2-heart v2-heart-${category}`;
        icon.textContent = category ? "♥" : "♡";
    }
    const row = print.closest("[data-collection-row]");
    if (row) renderCollectionHearts(row);
}

document.querySelectorAll("[data-collection-row]").forEach(renderCollectionHearts);

document.querySelectorAll("[data-print-id]").forEach((print) => {
    const button = print.querySelector("[data-category-button]");
    const menu = print.querySelector("[data-category-menu]");
    if (!button || !menu) return;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const opening = menu.hidden;
        closeCategoryMenus(menu);
        menu.hidden = !opening;
        button.setAttribute("aria-expanded", String(opening));
        if (opening) menu.querySelector(`[data-category-value="${print.dataset.category || 0}"]`)?.focus();
    });
    menu.querySelectorAll("[data-category-value]").forEach((option) => {
        option.addEventListener("click", (event) => {
            event.stopPropagation();
            setCollectionCategory(print, option.dataset.categoryValue);
            closeCategoryMenus();
            button.focus();
        });
    });
});

document.addEventListener("click", () => closeCategoryMenus());
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCategoryMenus();
});

document.querySelectorAll(".dynamicLink").forEach((element) => {
    element.addEventListener("click", function(event) {
        event.preventDefault();
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set("page", this.getAttribute("data-page"));
        window.location.href = currentUrl.toString();
    });
});

function sortTypeChange(type) {
    const sortInput = document.getElementById("id_sortValue");
    const searchForm = document.getElementById("검색폼");
    if (!sortInput || !searchForm) return;
    sortInput.value = type;
    searchForm.submit();
}

const currentSort = new URL(window.location.href).searchParams.get("sortValue") || "";
const sortName = document.getElementById("정렬카드명");
const sortCode = document.getElementById("정렬코드");

if (sortName) {
    sortName.classList.toggle("is-active", currentSort === "name");
    sortName.addEventListener("click", () => sortTypeChange(currentSort === "name" ? "" : "name"));
}

if (sortCode) {
    sortCode.classList.toggle("is-active", currentSort === "code");
    sortCode.addEventListener("click", () => sortTypeChange(currentSort === "code" ? "" : "code"));
}

const saveButton = document.getElementById("컬렉션수정버튼");
if (saveButton) {
    saveButton.addEventListener("click", () => {
        const updateForm = document.getElementById("컬렉션업데이트");
        if (!updateForm) return;

        const formData = new FormData(updateForm);
        const body = {
            collected: { ...changedCollection },
            categories: { ...changedCategories },
        };

        fetch(updateForm.action, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": formData.get("csrfmiddlewaretoken"),
            },
            body: JSON.stringify(body),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.result === "ok") {
                    Object.keys(changedCollection).forEach((key) => delete changedCollection[key]);
                    Object.keys(changedCategories).forEach((key) => delete changedCategories[key]);
                    saveButton.textContent = collectionText("saved", "저장됨");
                    window.setTimeout(() => {
                        saveButton.textContent = collectionText("save", "저장");
                    }, 1200);
                } else {
                    alert(data.message || collectionText("saveFailed", "저장에 실패했습니다."));
                }
            })
            .catch(() => {
                alert(collectionText("saveFailed", "저장에 실패했습니다."));
            });
    });
}
