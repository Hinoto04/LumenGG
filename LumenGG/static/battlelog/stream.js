var startAreaId = null; // 드래그 시작 영역 ID

function printMoveLog(startAreaId, dropAreaId, name) {
    //$('#logtext').append(
    //    '<div>' + startAreaId + ' → ' + dropAreaId + ' : ' + name + '</div>'
    //);
    //$('#logtext').scrollTop($('#logtext')[0].scrollHeight);
}

$(document).ready(function() {
    var card = $("#p1-card-1");

    for(var i = 0; i < 9; i++) {
        var copy = card.clone();

        $("#P1손패").append(copy);
    }
    for(var i = 0; i < 9; i++) {
        var copy = card.clone();
        $("#P1리스트").append(copy);
    }
    for(var i = 0; i < 6; i++) {
        var copy = card.clone();
        $("#P1사이드").append(copy);
    }

    $('.lmc-card').draggable({
        helper: 'clone',      // 드래그 시 실제 오브젝트가 아닌 복제본 사용
        revert: 'invalid',    // 드롭에 실패하면 원래 위치로 되돌림
        zIndex: 1000,
        start: function(event, ui) {
            // 드래그 시작 시 부모 영역의 id(class)를 저장
            // 가장 가까운 영역의 id나 class 등 원하는 정보로
            startAreaId = $(this).closest('.area, .card-area').attr('id');
        }
    });

    $('.card-area').droppable({
        accept: '.lmc-card',  // .lmc-card만 드롭 허용
        hoverClass: 'drop-hover', // 드래그 중일 때 시각적 효과
        drop: function(event, ui) {
            // 카드가 이동된 경우 원래 위치에서 제거하고, card-area에 추가
            let dropAreaId = $(this).attr('id');
            printMoveLog(startAreaId, dropAreaId, ui.draggable.text());
            $(this).append(ui.draggable);
        }
    });

});