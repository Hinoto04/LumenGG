function processCardLinks($editor) {
    let html = $editor.summernote('code');

    // 1. [[링크 텍스트|카드명]] 패턴
    let regexDouble = /\[\[([^\[\]\|]{1,30})\|([^\[\]\|]{1,30})\]\]/g;
    let matchesDouble = [...html.matchAll(regexDouble)];
    for (let match of matchesDouble) {
        let linkText = match[1];
        let cardName = match[2];
        $.ajax({
            url: '/deck/checkCardName',
            type: 'GET',
            data: { name: cardName },
            success: function(res) {
                let currentHtml = $editor.summernote('code');
                let link = `<a href="https://lumen.hinoto.kr/detail/${encodeURIComponent(cardName)}" target="_blank">${linkText}</a>`;
                let before = `[[${linkText}|${cardName}]]`;
                let idx = currentHtml.indexOf(before);
                if (idx !== -1) {
                    currentHtml = currentHtml.replace(before, link);
                    $editor.summernote('code', currentHtml);

                    // 커서를 변환된 링크 바로 뒤로 이동
                    setTimeout(function() {
                        let editorNode = $('.note-editable')[0];
                        if (!editorNode) return;
                        let walker = document.createTreeWalker(editorNode, NodeFilter.SHOW_ELEMENT, null, false);
                        let found = null;
                        while (walker.nextNode()) {
                            if (walker.currentNode.tagName === 'A' && walker.currentNode.href.endsWith(encodeURIComponent(cardName))) {
                                found = walker.currentNode;
                            }
                        }
                        if (found) {
                            let range = document.createRange();
                            range.setStartAfter(found);
                            range.collapse(true);
                            let sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }
                    }, 0);
                }
            },
            error: function(xhr) {
                if (xhr.status === 404) {
                    let currentHtml = $editor.summernote('code');
                    let fail = `[[${linkText}|${cardName}]`;
                    let before = `[[${linkText}|${cardName}]]`;
                    let idx = currentHtml.indexOf(before);
                    if (idx !== -1) {
                        currentHtml = currentHtml.replace(before, fail);
                        $editor.summernote('code', currentHtml);

                        // 커서를 변환된 텍스트 바로 뒤로 이동
                        setTimeout(function() {
                            let editorNode = $('.note-editable')[0];
                            if (!editorNode) return;
                            let walker = document.createTreeWalker(editorNode, NodeFilter.SHOW_ELEMENT, null, false);
                            let found = null;
                            while (walker.nextNode()) {
                                if (walker.currentNode.tagName === 'SPAN' && walker.currentNode.style.color === 'red' && walker.currentNode.textContent === cardName) {
                                    found = walker.currentNode;
                                }
                            }
                            if (found) {
                                let range = document.createRange();
                                range.setStartAfter(found);
                                range.collapse(true);
                                let sel = window.getSelection();
                                sel.removeAllRanges();
                                sel.addRange(range);
                            }
                        }, 0);
                    }
                }
            }
        });
    }

    // 2. [[카드명]] 패턴
    let regexSingle = /\[\[([^\[\]\|]{1,30})\]\]/g;
    let matchesSingle = [...html.matchAll(regexSingle)];
    for (let match of matchesSingle) {
        let cardName = match[1];
        $.ajax({
            url: '/deck/checkCardName',
            type: 'GET',
            data: { name: cardName },
            success: function(res) {
                let currentHtml = $editor.summernote('code');
                let link = `<a href="https://lumen.hinoto.kr/detail/${encodeURIComponent(cardName)}" target="_blank">${cardName}</a>`;
                let before = `[[${cardName}]]`;
                let idx = currentHtml.indexOf(before);
                if (idx !== -1) {
                    currentHtml = currentHtml.replace(before, link);
                    $editor.summernote('code', currentHtml);

                    // 커서를 변환된 링크 바로 뒤로 이동
                    setTimeout(function() {
                        let editorNode = $('.note-editable')[0];
                        if (!editorNode) return;
                        let walker = document.createTreeWalker(editorNode, NodeFilter.SHOW_ELEMENT, null, false);
                        let found = null;
                        while (walker.nextNode()) {
                            if (walker.currentNode.tagName === 'A' && walker.currentNode.href.endsWith(encodeURIComponent(cardName))) {
                                found = walker.currentNode;
                            }
                        }
                        if (found) {
                            let range = document.createRange();
                            range.setStartAfter(found);
                            range.collapse(true);
                            let sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }
                    }, 0);
                }
            },
            error: function(xhr) {
                if (xhr.status === 404) {
                    let currentHtml = $editor.summernote('code');
                    let fail = `[[${cardName}]`;
                    let before = `[[${cardName}]]`;
                    let idx = currentHtml.indexOf(before);
                    if (idx !== -1) {
                        currentHtml = currentHtml.replace(before, fail);
                        $editor.summernote('code', currentHtml);

                        // 커서를 변환된 텍스트 바로 뒤로 이동
                        setTimeout(function() {
                            let editorNode = $('.note-editable')[0];
                            if (!editorNode) return;
                            let walker = document.createTreeWalker(editorNode, NodeFilter.SHOW_ELEMENT, null, false);
                            let found = null;
                            while (walker.nextNode()) {
                                if (walker.currentNode.tagName === 'SPAN' && walker.currentNode.style.color === 'red' && walker.currentNode.textContent === cardName) {
                                    found = walker.currentNode;
                                }
                            }
                            if (found) {
                                let range = document.createRange();
                                range.setStartAfter(found);
                                range.collapse(true);
                                let sel = window.getSelection();
                                sel.removeAllRanges();
                                sel.addRange(range);
                            }
                        }, 0);
                    }
                }
            }
        });
    }
}

$(document).ready(function () {
    $('#id_description').summernote({
        placeholder: '내용을 입력해주세요.',
        height: 500,
        lang: 'ko-KR',
        toolbar: [
            ['style', ['style']],
            ['font', ['bold', 'underline', 'clear']],
            ['color', ['color']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['table', ['table']],
            ['insert', ['link', 'picture', 'video']],
            ['view', ['fullscreen', 'help']]
        ],
        callbacks: {
            onKeyup: function(e) {
                if (e.key === ']') {
                    processCardLinks($(this));
                }
            },
            onChange: function(contents, $editable) {
                // 모바일 대응: ']]'가 입력된 경우에만 실행
                var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
                        || window.innerWidth <= 768;
                if (!isMobile) return;
                if (contents.includes(']]')) {
                    processCardLinks($('#id_description'));
                }
            }
        }
    });
    $('p').css('margin-bottom','0')
});