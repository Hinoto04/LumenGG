var cardData = {}
var last = 0;

function showCardImg(id) {
    let i = id.split('_')[2];
    const tooltip = $('#tooltip');
    console.log(cardData[i]);
    tooltip.css('background-image', 'url('+cardData[i]['img'])+');';
    tooltip.show();
}

function cardSearch() {
    var formData = $("#cardSearchForm").serialize();
    $('#cardSearchResult').empty();
    $.ajax({
        type: 'GET',
        url: '/battlelog/cardLoad',
        data: formData,
        success: function(res) {
            let pState = $("#cardPlayerState option:selected").val();
            res.forEach(function(element) {
                cardData[last] = element
                cardData[last]['player'] = pState==1?1:2
                if(pState == 1) {
                    $("#cardSearchResult").append(`
                        <div class="lmc-card p1-card" id="card_id_${last}">${element.name}</div>
                        `);
                } else {
                    $("#cardSearchResult").append(`
                        <div class="lmc-card p2-card" id="card_id_${last}">${element.name}</div>
                        `);
                }
                
                last++;
            });
            $('.lmc-card').draggable({
                helper: 'clone',      // 드래그 시 실제 오브젝트가 아닌 복제본 사용
                revert: 'invalid',    // 드롭에 실패하면 원래 위치로 되돌림
                appendTo: 'body', 
                zIndex: 1000,
                start: function(event, ui) {
                    // 드래그 시작 시 부모 영역의 id(class)를 저장
                    // 가장 가까운 영역의 id나 class 등 원하는 정보로
                    $(ui.helper).css('z-index', 9999);
                    startAreaId = $(this).closest('.area, .card-area').attr('id');
                },
                stop: function(event, ui) {
                    // 드래그 종료 시 z-index를 원래 상태로 복원
                    $(ui.helper).css('z-index', 1000);
                }
            });
            $('.lmc-card').on('mouseenter', function(event) {
                showCardImg($(this).attr('id'));
            });

            $('.lmc-card').on('mouseleave', function() {
                $('#tooltip').hide(); // 마우스가 카드에서 나가면 툴팁 숨김
            });
        }
    });
}

function deckLoad() {
    var formData = $("#deckLoadForm").serialize();
    $.ajax({
        type: 'GET',
        url: '/battlelog/deckLoad',
        data: formData,
        success: function(res) {
            if(res.status == '404') return;
            let pState = $("#deckPlayerState option:selected").val();
            if(pState == 1) {
                $("#p1area > .card-area > .lmc-card").remove()
            } else {
                $("#p2area > .card-area > .lmc-card").remove();
            }
            //else $("#p2area > .card-area").clear()
            res.deck.forEach(function(element) {
                for(let i = 0;i<element.count;i++) {
                    let cdt = {
                        'name': element.card__name,
                        'img': element.card__img,
                        'player': pState==1?1:2,
                    }
                    cardData[last] = cdt;

                    let obj = null
                    if(pState == 1) 
                        obj = `<div class="lmc-card p1-card" id="card_id_${last}">${element.card__name}</div>`;
                    else
                        obj = `<div class="lmc-card p2-card" id="card_id_${last}">${element.card__name}</div>`;

                    let target = pState==1?'#P1':'#P2';
                    if(i < element.side)
                        target += '사이드'
                    else if(i < element.side+element.hand)
                        target += '손패'
                    else
                        target += '리스트'
                    $(target).append(obj);
                    
                    last++
                }
            });
            $('.lmc-card').draggable({
                helper: 'clone',      // 드래그 시 실제 오브젝트가 아닌 복제본 사용
                revert: 'invalid',    // 드롭에 실패하면 원래 위치로 되돌림
                appendTo: 'body', 
                zIndex: 1000,
                start: function(event, ui) {
                    // 드래그 시작 시 부모 영역의 id(class)를 저장
                    // 가장 가까운 영역의 id나 class 등 원하는 정보로
                    $(ui.helper).css('z-index', 9999);
                    startAreaId = $(this).closest('.area, .card-area').attr('id');
                },
                stop: function(event, ui) {
                    // 드래그 종료 시 z-index를 원래 상태로 복원
                    $(ui.helper).css('z-index', 1000);
                }
            });
            $('.lmc-card').on('mouseenter', function(event) {
                showCardImg($(this).attr('id'));
            });

            $('.lmc-card').on('mouseleave', function() {
                $('#tooltip').hide(); // 마우스가 카드에서 나가면 툴팁 숨김
            });
        }
    });
}

$(document).ready(function() {
    $("#loadDeckBtn").on('click', function() {
        $(".functionTab").hide();
        $("#deckFunction").show();
    })
    $("#loadCardBtn").on('click', function() {
        $(".functionTab").hide();
        $("#cardFunction").show();
    })
    $("#LogBtn").on('click', function() {
        $(".functionTab").hide();
        $("#logFunction").show();
    })

    $("#deckLoadForm").keydown(function(event) {
        if(event.keyCode == '13') {
            event.preventDefault();
            return;
        }
    })

    $("#cardSearchForm").keydown(function(event) {
        if(event.keyCode == '13') {
            event.preventDefault();
            return;
        }
    });

    $('#cardSearchBtn').on('click', function() { cardSearch()});
    $('#deckLoadBtn').on('click', function() { deckLoad()});
});

