const changedCollection = {};

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
                    saveButton.textContent = "저장됨";
                    window.setTimeout(() => {
                        saveButton.textContent = "저장";
                    }, 1200);
                } else {
                    alert(data.message || "저장에 실패했습니다.");
                }
            })
            .catch(() => {
                alert("저장에 실패했습니다.");
            });
    });
}
