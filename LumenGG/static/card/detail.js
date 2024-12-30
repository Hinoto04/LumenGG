$("#kwSelect").on("change", function() {
    $('.relationBox').hide();
    $("#"+$(this).val()).show();
})

//console.log($("#kwSelect").val())
$("#"+$("#kwSelect").val()).show();