$(".별점").each(function(index, item) {
    let score = Number($(item).text())
    let text = ""
    for(let i=0;i<score;i++) {
        text += `<span class="fa fa-star checked"></span>`
    }
    for(let i=score;i<10;i++) {
        text += `<span class="fa fa-star"></span>`
    }
    $(item).text("");
    $(item).append(text);
});

$(document).ready(function(){
    // Check Radio-box
    $(".rating input:radio").attr("checked", false);

    $('.rating input').click(function () {
        $(".rating span").removeClass('checked');
        $(this).parent().addClass('checked');
    });
});

$('input[type="text"]').keydown(function(event) {
    if (event.keyCode === 13) {
        event.preventDefault();
    }
});