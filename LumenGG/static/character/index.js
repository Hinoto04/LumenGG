var charDatas = {

}

const lumenText = window.lumenLanguageText || {};
function t(key, fallback) {
    return lumenText[key] || fallback;
}

//그래프 세팅용
function HexToRGB(hex, alpha) {
    let r = parseInt(hex.slice(1, 3), 16),
        g = parseInt(hex.slice(3, 5), 16),
        b = parseInt(hex.slice(5, 7), 16);

    if (alpha) {
        return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
    } else {
        return "rgb(" + r + ", " + g + ", " + b + ")";
    }
}

function pickDisplaySet(windowSize) {
    if(windowSize > 1200) 
        windowSize = 1200;
    if(windowSize > 768)
        $("#픽창").css("--size", ((windowSize*0.7)-5*11)/12 + 'px');
    else
        $("#픽창").css("--size", (768-5*11)/12 + 'px');
}

const isV2CharacterPage = document.querySelector(".v2-character-page") !== null;
const ctx = $("#캐릭터그래프")[0].getContext('2d');

function v2CssVar(name, fallback) {
    if (!isV2CharacterPage) {
        return fallback;
    }
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
}

function applyGraphTheme() {
    if (!isV2CharacterPage || !graph) {
        return;
    }
    const scale = graph.options.scales.r;
    scale.grid.color = v2CssVar("--v2-line", "rgba(244, 241, 234, .16)");
    scale.angleLines.color = v2CssVar("--v2-line", "rgba(244, 241, 234, .16)");
    scale.ticks.color = v2CssVar("--v2-muted", "#b8b0a4");
    scale.ticks.backdropColor = "transparent";
    scale.ticks.font = {
        weight: "800",
    };
    scale.pointLabels.color = v2CssVar("--v2-text", "#f4f1ea");
    scale.pointLabels.font = {
        size: 16,
        weight: "900",
    };
    graph.update("none");
}

const graph = new Chart(ctx, {
    type: 'radar',
    data: {
        labels: [t('power', '화력'), t('combo', '연계'), t('reversal', '변수창출'), t('safety', '안정성'), t('tempo', '템포')],
        datasets: [{
            label: t('data', '데이터'),
            data: [0, 0, 0, 0, 0],
            fill: true,
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            borderColor: 'rgb(255, 99, 132)',
        }]
    },
    options: {
        responsive: false,
        scales: {
            r: {
                suggestedMin: 0,
                suggestedMax: 10,
                grid: {
                    color: isV2CharacterPage ? v2CssVar("--v2-line", "rgba(244, 241, 234, .16)") : undefined,
                },
                angleLines: {
                    color: isV2CharacterPage ? v2CssVar("--v2-line", "rgba(244, 241, 234, .16)") : undefined,
                },
                ticks: {
                    stepSize: 2,
                    color: isV2CharacterPage ? v2CssVar("--v2-muted", "#b8b0a4") : undefined,
                    backdropColor: isV2CharacterPage ? 'transparent' : undefined,
                    font: isV2CharacterPage ? {
                        weight: "800",
                    } : undefined,
                },
                pointLabels: {
                    color: isV2CharacterPage ? v2CssVar("--v2-text", "#f4f1ea") : undefined,
                    font: {
                        size: 16,
                        weight: isV2CharacterPage ? "900" : undefined,
                    }
                }
            },
        },
        plugins: {
            legend: {
                display: false,
            }
        }
    },
})

if (isV2CharacterPage) {
    applyGraphTheme();
    new MutationObserver(applyGraphTheme).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
    });
}

//카드이미지 변경용
var passiveOn = false;
var skinIndex = 0;
var skinList = [];
var tokenIndex = -1;
var tokenList = [];
var passiveImg = "";

function skinChange(change) {
    if (!skinList.length)
        return;
    passiveOn = false;
    if(change)
        skinIndex = (skinIndex+1)%skinList.length;
    $("#캐릭터카드 > img").attr("src", skinList[skinIndex]);
}

function tokenChange(change) {
    if (!tokenList.length)
        return;
    passiveOn = false;
    if(change || tokenIndex < 0)
        tokenIndex = (tokenIndex+1)%tokenList.length;
    $("#캐릭터카드 > img").attr("src", tokenList[tokenIndex]);
}

function passiveChange() {
    if(!passiveImg)
        return;
    if(passiveOn) {
        passiveOn = false;
        skinChange(0);
    } else {
        passiveOn = true;
        $("#캐릭터카드 > img").attr("src", passiveImg);
    }
}

//페이지 변경용
var nowPage = 0;
var pageId = ["#그래프", "#상징카드정보"]
var pageName = [t('graph', '그래프'), t('keyCards', '중요한 카드')]
var pageType = ['flex', 'grid']
function nextPage() {
    $(pageId[nowPage]).css("display", "none");
    nowPage = (nowPage+1)%pageId.length;
    $(pageId[nowPage]).css("display", pageType[nowPage]);
    $("#페이지명").text(pageName[nowPage]);
}
function previousPage() {
    $(pageId[nowPage]).css("display", "none");
    nowPage = (nowPage+pageId.length-1)%pageId.length;
    $(pageId[nowPage]).css("display", pageType[nowPage]);
    $("#페이지명").text(pageName[nowPage]);
}

function commentLoad(commentList) {
    $("#댓글목록").empty();
    const isV2 = $("#댓글목록").hasClass("v2-character-comments");
    $.each(commentList, function(index, item) {
        if (isV2) {
            $("#댓글목록").append(`
                <div class="v2-character-comment v2-panel">
                    <div class="v2-character-comment-head">
                        <a href="/common/v2/profile/${encodeURIComponent(item.author_name)}/">${item.author_name}</a>
                        <div class="v2-character-comment-scores">
                            <span>${t('power', '화력')} ${item.power?item.power:t('unrated', '미평가')}</span>
                            <span>${t('combo', '연계')} ${item.combo?item.combo:t('unrated', '미평가')}</span>
                            <span>${t('variable', '변수')} ${item.reversal?item.reversal:t('unrated', '미평가')}</span>
                            <span>${t('stable', '안정')} ${item.safety?item.safety:t('unrated', '미평가')}</span>
                            <span>${t('tempo', '템포')} ${item.tempo?item.tempo:t('unrated', '미평가')}</span>
                        </div>
                    </div>
                    <p>${item.comment.replace('\n', '<br>')}</p>
                </div>
            `)
        } else {
            $("#댓글목록").append(`
                <div class="댓글 배경색1 mb-2">
                    <div class="d-flex flex-wrap">
                        <div class="me-2"><a href="/common/profile/${item.author_name}">
                            ${item.author_name} | </a></div>
                        <div class="점수 flex-grow-1">
                            <div>${t('power', '화력')} : ${item.power?item.power:t('unrated', '미평가')}</div>
                            <div>${t('combo', '연계')} : ${item.combo?item.combo:t('unrated', '미평가')}</div>
                            <div>${t('reversal', '변수창출')} : ${item.reversal?item.reversal:t('unrated', '미평가')}</div>
                            <div>${t('safety', '안정성')} : ${item.safety?item.safety:t('unrated', '미평가')}</div>
                            <div>${t('tempo', '템포')} : ${item.tempo?item.tempo:t('unrated', '미평가')}</div>
                        </div>
                    </div>
                    <div class="ms-2">${item.comment.replace('\n', '<br>')}</div>
                </div>
            `)
        }
    })
    
}

function dataSet(id) {
    graph.data.datasets[0].data = charDatas[id].char.datas.graph;
    graph.data.datasets[0].label = charDatas[id].char.name;
    graph.data.datasets[0].backgroundColor = HexToRGB(charDatas[id].char.color, 0.2);
    graph.data.datasets[0].borderColor = charDatas[id].char.color;
    graph.update();

    skinIndex = 0;
    skinList = charDatas[id].skin;
    tokenIndex = -1;
    tokenList = charDatas[id].token || [];
    passiveOn = false;
    passiveImg = charDatas[id].passive.length ? charDatas[id].passive[0].img : "";
    $("#passiveChange").prop("disabled", !passiveImg);
    $("#skinChange").prop("disabled", skinList.length <= 1);
    $("#tokenChange").prop("disabled", tokenList.length < 1);

    skinChange(0);
    $("#캐릭터이름").text(charDatas[id].char.name);
    $("#캐릭터그룹").text(charDatas[id].char.group);
    $("#id_character").val(id);
    if(charDatas[id].selfComment) {
        let sc = charDatas[id].selfComment;
        $("#id_comment").val(sc.comment)
        $("#id_power").val(sc.power?sc.power:-1)
        $("#id_combo").val(sc.combo?sc.combo:-1)
        $("#id_reversal").val(sc.reversal?sc.reversal:-1)
        $("#id_safety").val(sc.safety?sc.safety:-1)
        $("#id_tempo").val(sc.tempo?sc.tempo:-1)
    }else {
        $("#id_comment").val("")
        $("#id_power").val(-1)
        $("#id_combo").val(-1)
        $("#id_reversal").val(-1)
        $("#id_safety").val(-1)
        $("#id_tempo").val(-1)
    }
    commentLoad(charDatas[id].comments)

    $("#상징1 > img").attr("src", charDatas[id].char.datas.identity[0].card[0].img_mid)
    $("#상징1 > p").text(charDatas[id].char.datas.identity[0].text)
    $("#상징2 > img").attr("src", charDatas[id].char.datas.identity[1].card[0].img_mid)
    $("#상징2 > p").text(charDatas[id].char.datas.identity[1].text)
    $("#상징3 > img").attr("src", charDatas[id].char.datas.identity[2].card[0].img_mid)
    $("#상징3 > p").text(charDatas[id].char.datas.identity[2].text)

    $("#특징").text("");
    $("#특징").append(charDatas[id].char.datas.playing);
    $(".pickImg").removeClass('selected');
    $(".pickImg").filter(function() {
        return $(this).attr("alt") == String(id);
    }).addClass('selected');
}

function dataLoad(id) {
    if(charDatas[id]) {
        dataSet(id);
        return;
    }
    $.ajax({
        type: 'GET',
        url: '/character/' + String(id),
        contentType: 'application/json',
        success: function(res) {
            charDatas[id] = res;
            dataSet(id);
        },
        error: function(xhr, status, error) {
            console.log(error);
        },
    });
}

$(document).ready(function() {
    // 초기 변수 설정
    let windowWidth = $(window).width();
    pickDisplaySet(windowWidth);

    // 초기 크기 출력
    //console.log(`Initial Width: ${windowWidth}`);

    // resize 이벤트 핸들러
    $(window).resize(function() {
        windowWidth = $(window).width();
        pickDisplaySet(windowWidth);
        //console.log(`Width: ${windowWidth}`);
    });

    $("#passiveChange").click(function() {
        passiveChange()
    });
    $("#skinChange").click(function() {
        skinChange(1)
    });
    $("#tokenChange").click(function() {
        tokenChange(1)
    });
    $("#previousPage").click(function() {
        previousPage();
    })
    $("#nextPage").click(function() {
        nextPage();
    })

    $(".pickImg").each(function(index, item) {
        let id = $(item).attr("alt")
        $(item).click(function() {
            dataLoad(id);
            $(".pickImg").removeClass('selected');
            $(item).addClass('selected');
        })
    })
});
