document.querySelectorAll(".dynamicLink").forEach((element) => {
    element.addEventListener("click", function(event) {
        event.preventDefault();
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set("page", this.getAttribute("data-page"));
        window.location.href = currentUrl.toString();
    });
});
