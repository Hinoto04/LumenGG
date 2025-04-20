
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
    if(windowSize > 1200) windowSize = 1200;
    $("#픽창").css("--size", ((windowSize*0.7)-5*11)/12 + 'px');
}

const ctx = $("#캐릭터그래프")[0].getContext('2d');
const graph = new Chart(ctx, {
    type: 'radar',
    data: {
        labels: ['화력', '연계', '변수창출', '안정성', '템포'],
        datasets: [{
            label: "데이터",
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
                ticks: {
                    stepSize: 2,
                },
                pointLabels: {
                    font: {
                        size: 16,
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

//카드이미지 변경용
var passiveOn = false;
var skinIndex = 0;
var skinList = [];
var passiveImg = "";

function skinChange(change) {
    if(change)
        skinIndex = (skinIndex+1)%skinList.length;
    $("#캐릭터카드 > img").attr("src", skinList[skinIndex]);
}

function passiveChange() {
    if(passiveOn)
        skinChange(0);
    else 
        $("#캐릭터카드 > img").attr("src", passiveImg);
    passiveOn = !passiveOn
}

//페이지 변경용
var nowPage = 0;
var pageId = ["#그래프", "#상징카드정보"]
var pageName = ["그래프", "중요한 카드"]
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

function dataLoad(id) {
    $.ajax({
        type: 'GET',
        url: '/character/' + String(id),
        contentType: 'application/json',
        success: function(res) {
            console.log(res);
            graph.data.datasets[0].data = res.char.datas.graph;
            graph.data.datasets[0].label = res.char.name;
            graph.data.datasets[0].backgroundColor = HexToRGB(res.char.color, 0.2);
            graph.data.datasets[0].borderColor = res.char.color;
            graph.update();

            skinIndex = 0;
            skinList = res.skin;
            passiveOn = false;
            passiveImg = res.passive[0].img

            skinChange(0);

            $("#상징1 > img").attr("src", res.char.datas.identity[0].card[0].img_mid)
            $("#상징1 > p").text(res.char.datas.identity[0].text)
            $("#상징2 > img").attr("src", res.char.datas.identity[1].card[0].img_mid)
            $("#상징2 > p").text(res.char.datas.identity[1].text)
            $("#상징3 > img").attr("src", res.char.datas.identity[2].card[0].img_mid)
            $("#상징3 > p").text(res.char.datas.identity[2].text)
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
    // 캐릭터 데이터 불러오기
    dataLoad(2);

    $("#passiveChange").click(function() {
        passiveChange()
    });
    $("#skinChange").click(function() {
        skinChange(1)
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