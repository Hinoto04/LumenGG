$("img.needLoadingImg").each(function() {
    $(this).on('load', function() {
        $(this).css('display', 'block');
        $(this).parent().find('.loading').css('display', 'none');
    });
});