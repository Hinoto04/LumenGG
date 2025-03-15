var cardList = [];
var relationList = {};

function cardSearch() {

    if($("#keyword").val().length < 2) {
        alert("검색어는 2글자 이상이어야 합니다.");
        return;
    }

    var formData = $("#cardSearchForm").serialize();
    
    $('#TextResult').empty();
    $.ajax({
        type: 'GET',
        url: '/qna/createSearch',
        data: formData,
        success: function(res) {
            let a = JSON.parse(res);
            a.sort(function(i, j) {
                return i["fields"]["frame"] - j["fields"]["frame"]
            })
            cardList = [...a];
            $("#ImageResult > div").css("grid-template-columns", "repeat(" + String(Math.ceil(a.length/3)) + ", 120px)")
            for(let i=0;i<a.length;i++) {
                $("#TextResult").append(`
                    <div id="card_text_${a[i]["pk"]}" class='resultCardText 배경색1'>
                        ${a[i]["fields"]["name"]}
                    </div>
                    `);
                $(`#card_text_${a[i]["pk"]}`).on('click', function(event) {
                    Increase(a[i]["pk"])});
                $(`#card_text_${a[i]["pk"]}`).on('contextmenu', function(event) {
                    event.preventDefault();
                    Decrease(a[i]["pk"])
                });
            }
        }
    })
}

function Increase(pk) {
    if(relationList[pk] == undefined) {
        relationList[pk] = 1;

        var a;
        for(let i=0;i<cardList.length;i++) {
            if(cardList[i]["pk"] == pk) {
                a = cardList[i];
            }
        }

        $("#RelationList").append(`
            <div id="card_text_added_${a["pk"]}" class='resultCardText 배경색1'>
                ${a["fields"]["name"]}
            </div>
            `);
        $(`#card_text_added_${a["pk"]}`).on('click', function(event) {
            Decrease(a["pk"])
        });
    }
}

function Decrease(pk) {
    if(relationList[pk] != undefined) {
        delete relationList[pk];
        $(`#card_text_added_${pk}`).remove();
    }
}

function qnaSubmit() {
    let formData = new FormData($("#submitForm")[0]);
    var object = {};
    formData.forEach((value, key) => object[key] = value);

    var arr = [];
    for (var key in relationList) {
        if (relationList.hasOwnProperty(key)) {
            arr.push( [ key, relationList[key] ] );
        }
    }

    let csrftoken = object['csrfmiddlewaretoken'];
    object['related'] = arr;
    var json = JSON.stringify(object);

    $.ajax({
        type: 'POST',
        url: '',
        contentType: 'application/json',
        data: json,
        headers: {"X-CSRFToken": csrftoken},
        success: function(res) {
            if(res.status == 100) {
                window.location.href = res.url;
            } else {
                alert(res.msg);
            }
        },
        error: function(xhr, status, error) {
            console.log(error);
        },
    })
}