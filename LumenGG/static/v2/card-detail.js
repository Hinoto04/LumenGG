(() => {
    const cardImage = document.getElementById("v2CardImage");
    const openButton = document.querySelector("[data-card-edition-open]");
    const modal = document.getElementById("cardEditionModal");
    const backdrop = document.querySelector(".v2-card-edition-backdrop");
    const editionOptions = Array.from(document.querySelectorAll("[data-card-edition-option]"));
    const releaseOptions = Array.from(document.querySelectorAll("[data-card-release-option]"));
    if (!cardImage) return;

    let lastFocused = null;

    function imageKey(value) {
        try {
            return new URL(value || "", document.baseURI).href;
        } catch (error) {
            return value || "";
        }
    }

    function updateSelection(option) {
        const selectedImage = imageKey(option?.dataset.image);
        const selectedCode = option?.dataset.code || "";
        const selectedEdition = option?.matches("[data-card-edition-option]")
            ? option
            : editionOptions.find((candidate) => (
                candidate.dataset.code === selectedCode
                && imageKey(candidate.dataset.image) === selectedImage
            ));

        editionOptions.forEach((option) => {
            const selected = option === selectedEdition;
            option.classList.toggle("is-selected", selected);
            option.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        releaseOptions.forEach((option) => {
            const selected = option.dataset.code === selectedCode;
            option.classList.toggle("is-selected", selected);
            option.setAttribute("aria-pressed", selected ? "true" : "false");
        });

        const labelNode = openButton?.querySelector("[data-card-edition-label]");
        if (labelNode && option?.dataset.label) {
            labelNode.textContent = option.dataset.label;
        }
    }

    function selectEdition(option) {
        const image = option.dataset.image || "";
        if (!image) return;
        cardImage.classList.add("is-switching");
        const settleImage = () => {
            cardImage.classList.remove("is-switching");
        };
        cardImage.addEventListener("load", settleImage, { once: true });
        cardImage.addEventListener("error", settleImage, { once: true });
        cardImage.src = image;
        updateSelection(option);
    }

    function openModal() {
        if (!modal || !backdrop) return;
        lastFocused = document.activeElement;
        modal.hidden = false;
        backdrop.hidden = false;
        document.body.classList.add("v2-card-edition-open");
        const selected = modal.querySelector(".v2-card-edition-option.is-selected");
        (selected || modal.querySelector("[data-card-edition-option]") || modal).focus();
    }

    function closeModal() {
        if (!modal || !backdrop) return;
        modal.hidden = true;
        backdrop.hidden = true;
        document.body.classList.remove("v2-card-edition-open");
        if (lastFocused instanceof HTMLElement) lastFocused.focus();
    }

    openButton?.addEventListener("click", openModal);
    document.querySelectorAll("[data-card-edition-close]").forEach((button) => {
        button.addEventListener("click", closeModal);
    });
    editionOptions.forEach((option) => {
        option.addEventListener("click", () => {
            selectEdition(option);
            closeModal();
        });
    });
    releaseOptions.forEach((option) => {
        option.addEventListener("click", () => selectEdition(option));
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal && !modal.hidden) closeModal();
    });

    const initialEdition = editionOptions.find((option) => option.classList.contains("is-selected"));
    if (initialEdition) updateSelection(initialEdition);
})();
