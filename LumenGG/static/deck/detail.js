// function splitElements() {
//     const $original = $('#original');    // 원래 요소를 담고 있는 div
//     const $children = $original.children(); // 모든 자식 요소를 가져옴
//     const $top = $('#listtop');              // 위쪽 div
//     const $bottom = $('#listbottom');        // 아래쪽 div
    
//     const midPoint = Math.ceil($children.length / 2); // 중간 지점 계산
  
//     // 위쪽 div에 요소 추가
//     $children.slice(0, midPoint).appendTo($top);
  
//     // 아래쪽 div에 요소 추가
//     $children.slice(midPoint).appendTo($bottom);
    
//     // 오리지널 제거
//     $original.remove()
// }

  // 함수 실행
//splitElements();

$(document).ready(function() {
    $('.hoverOn').each(function () {

        // Hover 이벤트 설정
        $(this).hover(
            function () {
                if(window.innerWidth > 768) { // 함수 호출 시 마다 창의 너비 확인
                    const childHeight = $(this).find('.sideImg').outerHeight(); // 자식 요소 높이 계산
                    $(this).css('height', childHeight); // 부모 높이를 증가
                }
            },
            function () {
                if(window.innerWidth > 768) { // 함수 호출 시 마다 창의 너비 확인
                    $(this).css('height', "10%"); // 부모 높이를 초기 높이로 복원
                }
            }
        );
    });
});

var deckDisplay = 'image';

function deckToggle() {
    if (deckDisplay == 'image') {
        $("#ImageDisplay").hide();
        $("#TextDisplay").show();
        $("#displayToggleBtn").text('이미지로 보기');
        deckDisplay = 'text';
    } else {
        $("#ImageDisplay").show();
        $("#TextDisplay").hide();
        $("#displayToggleBtn").text('텍스트로 보기');
        deckDisplay = 'image';
    }
}

function deckCopy() {
    var deckList = "";
    $("#텍스트리스트전체 > tbody > tr > th > a").each(function(index, item) {
        deckList += String(index+1) + ". " + item.text + "\n";
    });
    console.log(deckList);
    window.navigator.clipboard.writeText(deckList).then(() => {
        alert("클립보드에 복사되었습니다!")
    });
}

function deckCapture() {
    if (deckDisplay != 'image') {
        deckToggle();
    }
    const captureArea = document.getElementById('ImageDisplay');
    html2canvas(captureArea, {
        useCORS: true,
        allowTaint: true,
        scale: 2,
    }).then(canvas => {
        // 캔버스를 이미지로 변환
        const image = canvas.toDataURL('image/png');
        // 이미지 다운로드 링크 생성
        const link = document.createElement('a');
        link.href = image;
        link.download = 'captured-image.png';
        link.click();
    });
}