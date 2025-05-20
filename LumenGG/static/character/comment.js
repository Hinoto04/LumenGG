

$(document).ready(function() {
    $('#코멘트작성').submit(function() { // catch the form's submit event
        $.ajax({ // create an AJAX call...
            data: $(this).serialize(), // get the form data
            type: $(this).attr('method'), // GET or POST
            url: $(this).attr('action'), // the file to call
            success: function(response) { // on success..
                if(response == "성공")
                    alert('코멘트가 작성되었습니다. \n코멘트 반영에는 다소 시간이 걸릴 수 있습니다.')
                else
                    alert('코멘트 작성에 실패했습니다. \n반복된다면 운영자에게 문의 바랍니다.')
            }
        });
        return false;
    });
});
