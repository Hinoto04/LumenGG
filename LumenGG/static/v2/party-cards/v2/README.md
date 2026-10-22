# 루멘 파티 카드 이미지 v2

출처: `output/pdf/lumen-party-cards-v2/cards/`. 제공된 PNG를 변경 없이 복사했습니다.
아이템 앞면 13장, 이벤트 앞면 8장, 공통 뒷면 2장입니다.

설명란은 비어 있습니다. 문구는 `battlelog.PartyCard.effect_text`에 저장하고
웹·모바일 API에서 이미지 경로와 `effect_box` 좌표를 함께 제공합니다.
클라이언트는 해당 좌표에 별도 텍스트를 표시합니다. 이미지는 재생성하지 않습니다.

`card-data.json`은 원본 좌표·파일 대응 자료입니다. 그 안의 빈 `effectText`는 게임 문구가 아닙니다.
실제 문구는 Django 관리자 → 루멘 파티 카드에서 수정합니다.
