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

function parseDownloadFilename(contentDisposition, fallback) {
    if (!contentDisposition) return fallback;

    const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch) {
        try {
            return decodeURIComponent(encodedMatch[1].replace(/["]/g, ""));
        } catch (error) {
            return fallback;
        }
    }

    const match = contentDisposition.match(/filename="?([^"]+)"?/i);
    return match ? match[1] : fallback;
}

function setDeckCaptureLoading(link, isLoading) {
    const loadingText = "이미지 생성 중...";
    if (isLoading) {
        link.dataset.originalText = link.textContent;
        link.textContent = loadingText;
        link.dataset.captureLoading = "true";
        link.setAttribute("aria-busy", "true");
        link.setAttribute("aria-disabled", "true");
        link.classList.add("is-loading", "disabled");
    } else {
        link.textContent = link.dataset.originalText || "덱 캡쳐";
        delete link.dataset.captureLoading;
        link.removeAttribute("aria-busy");
        link.removeAttribute("aria-disabled");
        link.classList.remove("is-loading", "disabled");
    }
}

async function downloadDeckCapture(link) {
    const response = await fetch(link.href, {
        method: "GET",
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (!response.ok) {
        throw new Error(`capture failed: ${response.status}`);
    }

    const blob = await response.blob();
    const filename = parseDownloadFilename(
        response.headers.get("Content-Disposition"),
        "lumen-deck.png"
    );
    const objectUrl = URL.createObjectURL(blob);
    const downloadLink = document.createElement("a");
    downloadLink.href = objectUrl;
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function setupDeckCaptureDownloads() {
    document.querySelectorAll("[data-deck-capture-download]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (link.dataset.captureLoading === "true") {
                event.preventDefault();
                return;
            }

            if (!window.fetch || !window.URL || !window.URL.createObjectURL) {
                alert("덱 캡쳐 이미지를 생성합니다. 잠시만 기다려주세요.");
                return;
            }

            event.preventDefault();
            setDeckCaptureLoading(link, true);

            try {
                await downloadDeckCapture(link);
            } catch (error) {
                alert("덱 캡쳐 이미지 생성에 실패했습니다. 잠시 후 다시 시도해주세요.");
            } finally {
                setDeckCaptureLoading(link, false);
            }
        });
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
document.addEventListener("DOMContentLoaded", setupDeckCaptureDownloads);
