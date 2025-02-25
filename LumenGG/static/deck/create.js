var deckList = {
    //이후에 덱리스트가 추가될 dictionary
}

var cardList = [];
var listCount = 0;
var handCount = 0;
var sideCount = 0;
var maxDeckSize = 20;

var exceptList = {
    '175': 2,
    '256': 3,
    '212': 3,
    '323': 3,
    '321': 3,
    '231': 2,
    '236': 2
}

function ToggleDesc() {
    if($("#DescriptionInput").css('display') == 'none') {
        $("#DescriptionInput").show();
        $("#DescToggleBtn").text('▲ 덱 설명');
    } else {
        $("#DescriptionInput").hide();
        $("#DescToggleBtn").text('▼ 덱 설명');
    }
}

function textToggle() {
    if($("#TextResult").css('display') == 'none') {
        $("#ImageResult").hide();
        $("#TextResult").css('display', 'grid');
        $("#TextToggleBtn").text('이미지로 보기');
    } else {
        $("#TextResult").hide();
        $("#ImageResult").css('display', 'grid');
        $("#TextToggleBtn").text('텍스트로 보기');
    }
}

function charChange() {
    var selectedLabel = $(this).parent().text();
    if($(this).val() == 5) maxDeckSize = 23;
    else maxDeckSize = 20;
    $("input#char_main").attr('value', $(this).val());
    $("#char_main_box > label").text(selectedLabel);
    
    for(pk of Object.keys(deckList)) {
        let card = listSearch(pk)
        if(card['fields']['character'] != 1) {
            listCount -= deckList[pk]['count'];
            handCount -= deckList[pk]['hand'];
            sideCount -= deckList[pk]['side'];
            delete deckList[pk];
            $(`#in_deck_${pk}`).remove()
        }
    } 
}

$("input.charSelect").change(charChange);

function cardSearch() {
    var formData = $("#cardSearchForm").serialize();
    
    $('#ImageResult > div').remove()
    $('#ImageResult').append(`<div></div>`)
    $('#TextResult').empty();
    $.ajax({
        type: 'GET',
        url: '/deck/createSearch',
        data: formData,
        success: function(res) {
            let a = JSON.parse(res);
            a.sort(function(i, j) {
                return i["fields"]["frame"] - j["fields"]["frame"]
            })
            cardList = [...a];
            $("#ImageResult > div").css("grid-template-columns", "repeat(" + String(Math.ceil(a.length/3)) + ", 120px)")
            for(let i=0;i<a.length;i++) {
                $("#ImageResult > div").append(`
                    <div id="card_img_${a[i]["pk"]}" class='resultCard'>
                        <img class='cardImg needLoadingImg'
                        src="${a[i]["fields"]["img"]}"
                        alt="${a[i]["fields"]["name"]}">
                        <img class='cardImg loading'
                        src="${loadingImgLink}"></div>
                    `);
                $(".needLoadingImg").each(function() {
                    $(this).hide();
                    $(this).on('load', function() {
                        $(this).show();
                        $(this).parent().find('.loading').hide();
                    });
                });
                $(`#card_img_${a[i]["pk"]}`).on('click', function(event) {
                    Increase(a[i]["pk"])});
                $(`#card_img_${a[i]["pk"]}`).on('contextmenu', function(event) {
                    event.preventDefault();
                    Decrease(a[i]["pk"])
                });

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

function listSearch(pk) {
    for(let i=0;i<cardList.length;i++) {
        if(cardList[i]["pk"] == pk) {
            return cardList[i];
        }
    }
}

function getTemplate(pk) {
    return $(`
        <tr id="in_deck_${pk}">
            <td class="in_deck_cardname">${listSearch(pk)["fields"]["name"]}</th>
            <td>
                <button class="decrease btn p-0 btn-danger" onclick="Decrease('${pk}')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-dash-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M2 8a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 8"/>
                </svg></button>
                <p id="in_deck_count_${pk}" class="d-inline">1</p>
                <button class="increase btn p-0 btn-primary" onclick="Increase('${pk}')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2"/>
                </svg></button></th>
            <td>
                <button class="decrease btn p-0 btn-danger" onclick="sDecrease('${pk}', 'h')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-dash-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M2 8a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 8"/>
                </svg></button>
                    <p id="in_hand_count_${pk}" class="d-inline">0</p>
                <button class="increase btn p-0 btn-primary" onclick="sIncrease('${pk}', 'h')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2"/>
                </svg></button>
            </td>
            <td>
                <button class="decrease btn p-0 btn-danger" onclick="sDecrease('${pk}', 's')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-dash-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M2 8a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 8"/>
                </svg></button>
                <p id="in_side_count_${pk}" class="d-inline">0</p>
                <button class="increase btn p-0 btn-primary" onclick="sIncrease('${pk}', 's')">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2"/>
                </svg></button>
            </td>
        </tr>
    `)
}

function CountCheck() {
    $("#CardCount").text(listCount);
    $("#HandCount").text(handCount);
    $("#SideCount").text(sideCount);
}

function Increase(pk) {
    if(listCount>=maxDeckSize) {
        alert(`덱 매수는 최대 ${maxDeckSize}장입니다.`);
        return;
    }
    if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
        if(Object.keys(exceptList).includes(String(pk))) {
            if(deckList[pk]['count'] < exceptList[pk]) {
                deckList[pk]['count']++;
                $(`#in_deck_count_${pk}`).text(deckList[pk]['count'])
                listCount++;
            }
        }
    } else {
        deckList[pk] = {
            'count': 1,
            'hand': 0,
            'side': 0
        }
        listCount++;
        $("#MainDeckList").append(getTemplate(pk));
    }
    CountCheck();
}

function Decrease(pk) {
    if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
        if(deckList[pk]["count"] == 1) {
            handCount-=deckList[pk]['hand'];
            sideCount-=deckList[pk]['side'];
            delete deckList[pk]
            $(`#in_deck_${pk}`).remove()
        } else {
            deckList[pk]['count']--;
            handCount-=deckList[pk]['hand'];
            sideCount-=deckList[pk]['side'];
            deckList[pk]['hand']=0;
            deckList[pk]['side']=0;
            $(`#in_deck_count_${pk}`).text(deckList[pk]['count'])
            $(`#in_hand_count_${pk}`).text(0)
            $(`#in_side_count_${pk}`).text(0)
        }
        listCount--;
    }
    CountCheck();
}

function sIncrease(pk, mode) {
    if(mode == 'h') {
        if(handCount==5) {
            alert("손패 매수는 최대 5장입니다.");
            return;
        }
        if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
            if(deckList[pk]['hand'] + deckList[pk]['side'] < deckList[pk]['count']) {
                deckList[pk]['hand']++;
                $(`#in_hand_count_${pk}`).text(deckList[pk]['hand']);
                handCount++;
            } else {
                alert("손패와 사이드의 카드 갯수가 덱에 들어간 카드보다 많을 수 없습니다.");
                return
            }
        }
    } else if(mode == 's') {
        if(sideCount==9) {
            alert("사이드 매수는 최대 9장입니다.");
            return;
        }
        if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
            if(deckList[pk]['hand'] + deckList[pk]['side'] < deckList[pk]['count']) {
                deckList[pk]['side']++;
                $(`#in_side_count_${pk}`).text(deckList[pk]['side']);
                sideCount++;
            } else {
                alert("손패와 사이드의 카드 갯수가 덱에 들어간 카드보다 많을 수 없습니다.");
                return;
            }
        }
    }
    CountCheck();
}

function sDecrease(pk, mode) {
    if(mode == 'h') {
        if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
            if(deckList[pk]['hand'] >= 1) {
                deckList[pk]['hand']--;
                $(`#in_hand_count_${pk}`).text(deckList[pk]['hand']);
                handCount--;
            }
        }
    } else if(mode == 's') {
        if(Object.keys(deckList).includes(String(pk))) { //Key 존재 시,
            if(deckList[pk]['side'] >= 1) {
                deckList[pk]['side']--;
                $(`#in_side_count_${pk}`).text(deckList[pk]['side']);
                sideCount--;
            }
        }
    }
    CountCheck();
}

function deckSubmit() {
    let formData = new FormData($("#submitForm")[0]);
    var object = {};
    formData.forEach((value, key) => object[key] = value);

    var arr = [];
    for (var key in deckList) {
        if (deckList.hasOwnProperty(key)) {
            arr.push( [ key, deckList[key] ] );
        }
    }

    let csrftoken = object['csrfmiddlewaretoken'];
    object['deck'] = arr;
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