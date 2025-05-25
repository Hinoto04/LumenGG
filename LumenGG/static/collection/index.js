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
                if($(this).find('a').length) {
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
    var padding = 20;
    var mouseX = e.clientX, mouseY = e.clientY;
    var winW = window.innerWidth, winH = window.innerHeight;

    for (var i = 0; i < tooltips.length; i++) {
        var tooltip = tooltips[i];
        // 툴팁 크기 계산 (보이지 않을 때는 임의값 사용)
        var tooltipW = tooltip.offsetWidth || 200;
        var tooltipH = tooltip.offsetHeight || 200;

        var left = mouseX + padding;
        var top = mouseY + padding;

        // 오른쪽이 넘치면 왼쪽으로
        if (left + tooltipW > winW) left = mouseX - tooltipW - padding;
        if (left < 0) left = 0;

        // 아래가 넘치면 위로
        if (top + tooltipH > winH) top = mouseY - tooltipH - padding;
        if (top < 0) top = 0;

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }
};
// 컬렉션 수정 관련

var changedCollection = {};

function collectionUpdate() {
    let formData = new FormData($("#컬렉션업데이트")[0]);
    var object = {};
    formData.forEach((value, key) => object[key] = value);

    let csrftoken = object['csrfmiddlewaretoken'];
    object['collected'] = Object.assign({}, changedCollection);
    changedCollection = {};
    var json = JSON.stringify(object);

    console.log(json);

    $.ajax({
        type: 'POST',
        url: '/collection/update/',
        contentType: 'application/json',
        data: json,
        headers: {"X-CSRFToken": csrftoken},
        success: function(res) {
            if(res.status == 100) {
                window.location.href = res.url;
            } else {
                console.log(res);
            }
        },
        error: function(xhr, status, error) {
            console.log(error);
        },
    })
}


var nowSortType = '';

function sortTypeChange(t) {
    $("#id_sortValue").val(t);
    $("#검색폼").submit();
}

$(document).ready(function() {
    let currentUrl = new URL(window.location.href);

    nowSortType = currentUrl.searchParams.get('sortValue');
    if (nowSortType == 'name') {
        $("#정렬카드명").text('카드명 ▲');
    } else if (nowSortType == 'code') {
        $("#정렬코드").text('코드 ▲');
    }

    $("#컬렉션수정버튼").on('click', function() {
        collectionUpdate();
    });

    $("#정렬카드명").on('click', function() {
        if(nowSortType != 'name') {
            nowSortType = 'name';
            sortTypeChange('name');
        } else {
            nowSortType = '';
            sortTypeChange('');
        }
    })

    $("#정렬코드").on('click', function() {
        if(nowSortType != 'code') {
            nowSortType = 'code';
            sortTypeChange('code');
        } else {
            nowSortType = '';
            sortTypeChange('');
        }
    });
});

$(".cc_input").change(function() {
    let name = $(this).attr('name');
    let value = $(this).val();
    if(value < 0) {
        value = 0;
        $(this).val(0);
    } else if(value > 99) {
        value = 99;
        $(this).val(99);
    }

    changedCollection[name] = value;
    console.log(changedCollection);
})