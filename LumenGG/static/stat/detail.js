
function buildCharPie(chardata) {
    let xvalues = []
    let colors = []
    let yvalues = []

    chardata.forEach(element => {
        xvalues.push(element.name)
        colors.push(element.color)
        yvalues.push(element.used)
    });

    const charpi = new Chart("캐릭터파이", {
        type: "pie",
        data: {
            labels: xvalues,
            datasets: [{
                backgroundColor: colors,
                data: yvalues,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: "캐릭터 파이"
                }
            }
        }
    });
}

function buildSetsumeiPie(carddata) {
    let xvalues = []
    let yvalues = []

    carddata.forEach(card => {
        xvalues.push(card.name)
        yvalues.push(card.used)
    });

    const setsuBar = new Chart("중립카드사용률", {
        type: "bar",
        data: {
            labels: xvalues,
            datasets: [{
                label: "Dataset",
                data: yvalues,
            }]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                title: {
                    display: true,
                    text: "중립 카드 사용률",
                },
                legend: { display: false }
            },
            scales: {
                x: { min: 0 }
            }
        },
    })
}

$.ajax({
    url: loadUrl,
    method: 'get',
    success: function(data, status, xhr) {
        buildCharPie(data.chardata)
        buildSetsumeiPie(data.carddata)
    }
})