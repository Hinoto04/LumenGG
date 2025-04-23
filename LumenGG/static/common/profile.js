$(document).ready(function() {
    // #id_character select 요소의 값이 변경될 때
    $('#id_character').change(function() {
        // 폼을 제출합니다
        $('#프로필수정').submit();
    });
});