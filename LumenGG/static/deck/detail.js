function splitElements() {
    const $original = $('#original');    // 원래 요소를 담고 있는 div
    const $children = $original.children(); // 모든 자식 요소를 가져옴
    const $top = $('#listtop');              // 위쪽 div
    const $bottom = $('#listbottom');        // 아래쪽 div
    
    const midPoint = Math.ceil($children.length / 2); // 중간 지점 계산
  
    // 위쪽 div에 요소 추가
    $children.slice(0, midPoint).appendTo($top);
  
    // 아래쪽 div에 요소 추가
    $children.slice(midPoint).appendTo($bottom);
    
    // 오리지널 제거
    $original.remove()
  }
  
  // 함수 실행
  splitElements();