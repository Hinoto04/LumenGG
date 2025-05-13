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

var timeoutId = null; // 유예시간 타이머 ID
var nowControl = null;
var accumulatedValue = 0; // 버튼 안의 숫자 누적 값

function hpfpChange(type, sign, accsign, event, obj) {
    event.preventDefault(); // 기본 동작 방지
    let button = $(obj);
    if(nowControl == null)
        nowControl = button
    else if(nowControl.attr('id') != button.attr('id'))
        return;

    let num = (type=='HP'?100:1)*accsign;
    accumulatedValue += num; // 숫자 100 증가
    if(accumulatedValue<0) accumulatedValue=0;
    button.text(sign+accumulatedValue); // 버튼에 업데이트

    // 유예시간 타이머 초기화
    if (timeoutId) {
        clearTimeout(timeoutId);
    }

    // 2초 후 HP에 더하기
    timeoutId = setTimeout(function () {
        let hpElement = button.closest('.hpfpbox').find('.hpfp > span'); // HP 요소 찾기
        let player = hpElement.attr('id').substr(0,2);
        let currentHp = parseInt(hpElement.text()); // 현재 HP 가져오기
        hpElement.text(currentHp + accumulatedValue*Number(sign+'1')); // HP에 누적 값 더하기
        playerInfoChangeLog(type, player, accumulatedValue*Number(sign+'1'), hpElement.text());
        button.text(sign); // 버튼 숫자 초기화
        accumulatedValue = 0; // 누적 값 초기화
        nowControl = null;
    }, 1000);
}

$(document).ready(function () {
    // 왼쪽 클릭: 버튼 숫자 증가 및 유예시간 설정
    $('.hpfpbox > .hpin').on('click', function (event) {
        hpfpChange('HP', '+', +1, event, this);
    });
    $('.hpfpbox > .fpin').on('click', function (event) {
        hpfpChange('FP', '+', +1, event, this);
    });
    $('.hpfpbox > .hpde').on('click', function (event) {
        hpfpChange('HP', '-', +1, event, this);
    });
    $('.hpfpbox > .fpde').on('click', function (event) {
        hpfpChange('FP', '-', +1, event, this);
    });
    // 오른쪽 클릭: 버튼 숫자 감소
    $('.hpfpbox > .hpin').on('contextmenu', function (event) {
        hpfpChange('HP', '+', -1, event, this);
    });
    $('.hpfpbox > .fpin').on('contextmenu', function (event) {
        hpfpChange('FP', '+', -1, event, this);
    });
    $('.hpfpbox > .hpde').on('contextmenu', function (event) {
        hpfpChange('HP', '-', -1, event, this);
    });
    $('.hpfpbox > .fpde').on('contextmenu', function (event) {
        hpfpChange('FP', '-', -1, event, this);
    });

    $('#P1FPReset').on('click', function(event) {
        let fp = $(this).find('span').text();
        console.log(fp);
        $(this).find('span').text(0);
        console.log(Number(fp)*-1);
        playerFPResetLog('P1', Number(fp));
    });
    $('#P2FPReset').on('click', function(event) {
        let fp = $(this).find('span').text();
        $(this).find('span').text(0);
        playerFPResetLog('P2', Number(fp));
    });
});