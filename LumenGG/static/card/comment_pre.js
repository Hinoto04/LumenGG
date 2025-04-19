var score = 5;

function commentSubmit() {
    let formData = new FormData($("#코멘트작성")[0]);
    var object = {};
    formData.forEach((value, key) => object[key] = value);
    let csrftoken = object['csrfmiddlewaretoken'];

    if(!object['score']) {
        object['score'] = score;
    }

    var json = JSON.stringify(object);

    $.ajax({
        type: 'POST',
        url: '',
        contentType: 'application/json',
        data: json,
        headers: {"X-CSRFToken": csrftoken},
        success: function(res) {
            if(res.status == 100) {
                alert("코멘트가 작성되었습니다.\n코멘트는 반영까지 약간의 시간이 걸립니다.")
                $("코멘트작성").hide();
            } else {
                alert(res.msg);
            }
        },
        error: function(xhr, status, error) {
            console.log(error);
        },
    })
}