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
    $("#initValue").attr("checked", true);
    $("#initValue").parent().addClass('checked');

    $('.rating input').click(function () {
        $(".rating span").removeClass('checked');
        $(this).parent().addClass('checked');
    });
});