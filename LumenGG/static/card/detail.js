$("#kwSelect").on("change", function() {
    $('.관련상자').hide();
    $("#"+$(this).val()).css('display', 'grid');
})

//console.log($("#kwSelect").val())
$("#"+$("#kwSelect").val()).css('display', 'grid');

$("#카드이미지").on("click", function() {
    imageChange();
});