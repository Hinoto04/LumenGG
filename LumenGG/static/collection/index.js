var tooltips = document.querySelectorAll('.hoverImage span');

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
    let previousImageLink = '';
    let startIndex = null;
    let rowspan = 1;

    $('.merging').each(function(index) {
        const currentCardName = $(this).text();

        if (currentCardName === previousCardName) {
            rowspan++;
            let imageLink = $(this).find('img').attr('src');
            if (imageLink !== previousImageLink) {
                if($(this).find('a')) {
                    $(this).find('a').contents()[0].nodeValue = "(다른 판본)"; //요소 복사
                    $('.merging').eq(startIndex).find('div').append($(this).find('a').clone()); //요소 복사
                } else if($(this).find('p')) {
                    $(this).find('p').contents()[0].nodeValue = "(다른 판본)";
                    $('.merging').eq(startIndex).find('div').append($(this).find('p').clone()); //요소 복사
                }
                previousImageLink = imageLink; // 이미지 링크 업데이트
            }
            $(this).css('display', 'none'); // 동일한 카드명 셀 숨기기
        } else {
            // 새로운 카드명을 만났을 때 이전 카드명의 셀을 병합
            if (startIndex !== null) {
                $('.merging').eq(startIndex).css('grid-row-end', `span ${rowspan}`);
            }
            previousCardName = currentCardName;
            previousImageLink = $(this).find('img').attr('src');
            startIndex = index;
            rowspan = 1;
        }
    });

    // 마지막 그룹 병합 적용
    if (startIndex !== null) {
        $('.merging').eq(startIndex).css('grid-row-end', `span ${rowspan}`);
    }

    tooltips = document.querySelectorAll('.hoverImage span');
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

window.onmousemove = function (e) {
    var x = (e.clientX + 20) + 'px',
        y = (e.clientY + 20) + 'px';
    for (var i = 0; i < tooltips.length; i++) {
        tooltips[i].style.top = y;
        tooltips[i].style.left = x;
    }
};