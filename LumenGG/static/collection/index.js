var tooltips = document.querySelectorAll('.hoverImage span');

window.onmousemove = function (e) {
    var x = (e.clientX + 20) + 'px',
        y = (e.clientY + 20) + 'px';
    for (var i = 0; i < tooltips.length; i++) {
        tooltips[i].style.top = y;
        tooltips[i].style.left = x;
    }
};

$(document).ready(function() {
    $('#id_char > div > label').on('click', function(event) {
        const radioButton = $(this).find('input[type="radio"]');
        if (radioButton.prop('checked')) {
            radioButton.prop('checked', false);
            event.preventDefault(); // 기본 동작을 방지하여 선택 해제
        } else {
            radioButton.prop('checked', true);
        }
    });
});

$(document).ready(function() {
    let previousCardName = '';
    let startIndex = null;
    let rowspan = 1;

    $('.merging').each(function(index) {
        const currentCardName = $(this).text();

        if (currentCardName === previousCardName) {
            rowspan++;
            $(this).css('display', 'none'); // 동일한 카드명 셀 숨기기
        } else {
            // 새로운 카드명을 만났을 때 이전 카드명의 셀을 병합
            if (startIndex !== null) {
                $('.merging').eq(startIndex).css('grid-row-end', `span ${rowspan}`);
            }
            previousCardName = currentCardName;
            startIndex = index;
            rowspan = 1;
        }
    });

    // 마지막 그룹 병합 적용
    if (startIndex !== null) {
        $('.merging').eq(startIndex).css('grid-row-end', `span ${rowspan}`);
    }
});

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