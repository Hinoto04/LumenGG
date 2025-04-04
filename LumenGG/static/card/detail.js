$("#kwSelect").on("change", function() {
    $('.관련상자').hide();
    $("#"+$(this).val()).css('display', 'grid');
})

//console.log($("#kwSelect").val())
$("#"+$("#kwSelect").val()).css('display', 'grid');

var imgList = [];
var now = 0;

$("#카드이미지").on("click", function() {
    now++;
    if(now >= imgList.length) now = 0;
    $("#카드이미지").attr("src", imgList[now]);
});
