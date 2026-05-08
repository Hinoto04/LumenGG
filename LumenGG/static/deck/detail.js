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
    const captureArea = document.getElementById('v2DeckCaptureArea') || document.getElementById('ImageDisplay');
    const isV2Capture = captureArea && captureArea.id === 'v2DeckCaptureArea';
    html2canvas(captureArea, {
        useCORS: true,
        allowTaint: true,
        scale: 2,
        backgroundColor: isV2Capture ? '#111111' : '#ffffff',
        onclone: function(clonedDocument) {
            if (!isV2Capture) return;
            const clonedArea = clonedDocument.getElementById('v2DeckCaptureArea');
            if (clonedArea) {
                clonedArea.classList.add('is-capturing');
                clonedArea.style.background = '#111111';
                clonedArea.style.padding = '16px';
                const captureStyle = clonedDocument.createElement('style');
                captureStyle.textContent = `
                    .v2-deck-capture-area.is-capturing .v2-capture-text {
                        display: inline-flex !important;
                        align-items: center !important;
                        justify-content: center !important;
                        gap: 4px !important;
                        position: relative !important;
                        top: -2px !important;
                        line-height: 1 !important;
                    }
                    .v2-deck-capture-area.is-capturing .v2-capture-text strong {
                        line-height: 1 !important;
                    }
                `;
                clonedDocument.head.appendChild(captureStyle);

                const textTargets = clonedArea.querySelectorAll([
                    '.v2-chip',
                    '.v2-metric',
                    '.v2-deck-metric',
                    '.v2-unreleased',
                    '.v2-button',
                    '.v2-deck-version',
                    '.v2-deck-zone-head span'
                ].join(','));

                textTargets.forEach((element) => {
                    const wrapper = clonedDocument.createElement('span');
                    wrapper.className = 'v2-capture-text';
                    while (element.firstChild) {
                        wrapper.appendChild(element.firstChild);
                    }
                    element.appendChild(wrapper);

                    let height = 28;
                    if (element.classList.contains('v2-deck-metric')) height = 30;
                    if (element.classList.contains('v2-unreleased')) height = 24;
                    if (element.classList.contains('v2-button')) height = 36;
                    if (element.classList.contains('v2-deck-version')) height = 24;

                    element.style.display = 'inline-block';
                    element.style.boxSizing = 'border-box';
                    element.style.minHeight = '0';
                    element.style.height = `${height}px`;
                    element.style.paddingTop = '0';
                    element.style.paddingBottom = '0';
                    element.style.lineHeight = `${height - 2}px`;
                    element.style.textAlign = 'center';
                    element.style.verticalAlign = 'middle';
                });
            }
        },
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

$(document).ready(function () {
    // 이미지 캐시 딕셔너리
    const cardImgCache = {};

    // 툴팁 이미지 DOM 생성
    let $imgTooltip = $('<div id="card-hover-img-tooltip" style="position:fixed; display:none; z-index:9999; pointer-events:none;"><img src="" style="max-width:300px; max-height:400px; border:2px solid #333; background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.2);"></div>');
    $('body').append($imgTooltip);

    $('#덱설명').on('mouseenter', 'a', function (e) {
        let href = $(this).attr('href');
        // 맨 뒤에 슬래시가 있으면 제거
    if (href && href.endsWith('/')) {
        href = href.slice(0, -1);
    }
        let match = href && href.match(/^https:\/\/lumen\.hinoto\.kr\/detail\/(.+)$/);
        if (match) {
            let cardName = decodeURIComponent(match[1]);
            if (cardImgCache[cardName]) {
                $imgTooltip.find('img').attr('src', cardImgCache[cardName]);
                $imgTooltip.show();
            } else {
                $.get('/deck/detailHoverImg', { name: cardName })
                    .done(function (imgUrl) {
                        cardImgCache[cardName] = imgUrl;
                        $imgTooltip.find('img').attr('src', imgUrl);
                        $imgTooltip.show();
                    });
            }
        }
    }).on('mousemove', 'a', function (e) {
        // 툴팁 위치 조정 (화면 바깥으로 안나가게)
        if (window.innerWidth <= 768) return;
        let tooltip = $imgTooltip[0];
        let img = $imgTooltip.find('img')[0];
        let padding = 16;
        let mouseX = e.clientX, mouseY = e.clientY;
        let winW = window.innerWidth, winH = window.innerHeight;
        let imgW = img.naturalWidth || 300, imgH = img.naturalHeight || 400;
        let left = mouseX + padding, top = mouseY + padding;
        if (left + imgW > winW) left = mouseX - imgW - padding;
        if (left < 0) left = 0;
        if (top + imgH > winH) top = mouseY - imgH - padding;
        if (top < 0) top = 0;
        $imgTooltip.css({ left: left + 'px', top: top + 'px' });
    }).on('mouseleave', 'a', function () {
        $imgTooltip.hide();
        $imgTooltip.find('img').attr('src', '');
    });
});

function setV2SideZoneHeight() {
    const board = document.querySelector(".v2-deck-board");
    const list = document.querySelector(".v2-deck-zone-list");
    const hand = document.querySelector(".v2-deck-zone-hand");
    const side = document.querySelector(".v2-deck-zone-side");
    if (!board || !list || !hand || !side || window.innerWidth <= 980) {
        if (side) side.style.maxHeight = "";
        return;
    }

    const styles = window.getComputedStyle(board);
    const gap = parseFloat(styles.rowGap || styles.gap || "0") || 0;
    side.style.maxHeight = `${list.offsetHeight + hand.offsetHeight + gap}px`;
}

window.addEventListener("load", setV2SideZoneHeight);
window.addEventListener("resize", setV2SideZoneHeight);
document.addEventListener("DOMContentLoaded", setV2SideZoneHeight);
