var startAreaId = null; // 드래그 시작 영역 ID

$(document).ready(function() {
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

    $('.card-area').droppable({
        accept: '.lmc-card',  // .lmc-card만 드롭 허용
        hoverClass: 'drop-hover', // 드래그 중일 때 시각적 효과
        drop: function(event, ui) {
            // 카드가 이동된 경우 원래 위치에서 제거하고, card-area에 추가
            let dropAreaId = $(this).attr('id');
            writeCardLog(startAreaId, dropAreaId, ui.draggable.attr('id'));
            $(this).append(ui.draggable);
        }
    });

    $('.btlRstBtn').click(function() {
        $(this).parent().find('.lmc-card').each(function() {
            if($(this).hasClass('p1-card')) {
                writeCardLog($(this).parent().attr('id'), "P1리스트", $(this).attr('id'));
                $(this).appendTo('#P1리스트');
            } else if($(this).hasClass('p2-card')) {
                writeCardLog($(this).parent().attr('id'), "P2리스트", $(this).attr('id'));
                $(this).appendTo('#P2리스트');
            }
        });
    })
});