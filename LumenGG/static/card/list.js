document.querySelectorAll(".dynamicLink").forEach(element => {
    element.addEventListener('click', function(event) {
        event.preventDefault(); // 기본 동작 막기

        const currentUrl = new URL(window.location.href);
        const page = this.getAttribute('data-page'); // 클릭한 페이지 번호

        // 기존 GET 파라미터 유지 + page 파라미터 추가
        currentUrl.searchParams.set('page', page);
        console.log("Setted!");

        // 새로운 URL로 이동
        window.location.href = currentUrl.toString();
    });
});