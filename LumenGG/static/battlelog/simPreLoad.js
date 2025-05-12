var log = [];
var ptr = 0;

function reloadLog() {
    let logbox = $('#logtext');
    logbox.text('');
    log.forEach(function(element, index) {
        let boxbox = $(`<div class="logline"></div>`)
        logbox.append(boxbox);
        if(index == ptr-1) {
            boxbox.append('<div class="ptr">▶</div>');
        } else {
            boxbox.append('<div class="ptr"></div>');
        }
        if(element.type == 'CardMove')  {
            let id = element.card.split('_')[2];
            boxbox.append(`
                    <p class="${element.start.substr(0,2)}log">
                    <b>${element.start.substr(0,2)}</b>${element.start.substr(2)}</p><p> <b>→</b> </p>
                    <p class="${element.end.substr(0,2)}log">
                    <b>${element.end.substr(0,2)}</b>${element.end.substr(2)}</p><p> : </p>
                    <p class="P${cardData[id].player}log">${cardData[id].name}</p>
                `);
        } else if (['Phase', 'Turn', 'Etc'].indexOf(element.type) > -1) {
            boxbox.append(
                `<p>${element.text}</p>`
            )
        } else if(element.type == 'Action') {
            boxbox.append(`
                <p class="${element.player}log">
                    <b>${element.player}</b>${element.text}</p>`)
        }
        if(index == ptr-1) logbox.scrollTop($('#logtext')[0].scrollHeight);
    })
}

function writeCardLog(startAreaId, dropAreaId, cardId) {
    if(startAreaId == 'cardSearchResult' || dropAreaId == 'cardSearchResult') return;
    if(!(dropAreaId == 'P1배틀' || dropAreaId == 'P2배틀') && startAreaId == dropAreaId) return;
    log.splice(ptr, 0,
        {
            'type': 'CardMove',
            'start': startAreaId, 
            'end': dropAreaId, 
            'card': cardId
        });
    ptr++;
    reloadLog();
}

function writeTextLog(type, text) {
    log.splice(ptr, 0,
        {
            'type': type,
            'text': text,
        }
    )
    ptr++;
    reloadLog();
}

function writePhaseLog(phase) {
    writeTextLog('Phase', '------'+phase+' 페이즈------');
}

var turn = 1;
function writeTurnLog() {
    writeTextLog('Turn', '------Turn '+String(turn)+'------');
    turn++;
}

function writeEtcLog(text) {
    writeTextLog('Etc', text);
}

function playerActionLog(player, action) {
    log.splice(ptr, 0, {
        'type': 'Action',
        'player': player,
        'text': action,
    });
    ptr++;
    reloadLog();
}

$(document).ready(function() {
    $('#P1Action > button').each(function(index, item) {
        let text = $(item).text();
        $(item).on('click', function() {
            playerActionLog('P1', text);
        });
    });
    $('#P2Action > button').each(function(index, item) {
        let text = $(item).text();
        $(item).on('click', function() {
            playerActionLog('P2', text);
        });
    });
});