from django.db import models

# Create your models here.
class Character(models.Model):
    name = models.CharField(max_length=100) #캐릭터명
    description = models.TextField() #캐릭터 설명
    group = models.CharField(max_length=100) #캐릭터 소속 (루멘콘덴서, 뉴트럴 등)
    hp_hand = models.JSONField() #남은 체력 별 손 크기 제한
    img = models.URLField() #이미지 URL
    
    def __str__(self):
        return self.name

class Card(models.Model):
    name = models.CharField(max_length=100, blank=True) #카드명
    ruby = models.CharField(blank=True, max_length=100) #카드 루비(읽는 법)
    frame = models.SmallIntegerField(null=True, blank=True) #속도
    damage = models.IntegerField(null=True, blank=True) #대미지
    pos = models.CharField(max_length=3, null=True, blank=True) #판정 (상단, 중단, 하단)
    body = models.CharField(default='', max_length=10, null=True, blank=True) #부위 (손, 발)
    text = models.TextField(blank=True) #카드 효과
    hit = models.CharField(default=0, max_length=4, null=True, blank=True) #히트 시 프레임
    guard = models.CharField(default=0, max_length=4, null=True, blank=True) #가드 시
    counter = models.CharField(default=0, max_length=4, null=True, blank=True) #카운터 시
    special = models.CharField(null=True, blank=True, max_length=20) #특수판정
    g_top = models.CharField(null=True, blank=True, max_length=5) #상단방어
    g_mid = models.CharField(null=True, blank=True, max_length=5) #중단방어
    g_bot = models.CharField(null=True, blank=True, max_length=5) #하단방어
    type = models.CharField(default="공격", max_length=10, blank=True) #카드 종류 (공격, 수비, 특수 기술, 패시브)
    code = models.CharField(max_length=20, blank=True) #카드 일련번호 (UNC-AT-000)
    character = models.ForeignKey(Character, on_delete=models.PROTECT, related_name='cards', blank=True) #캐릭터
    img = models.URLField(blank=True) #이미지 URL
    hiddenKeyword = models.CharField(blank=True, default='', max_length=255) #이 카드를 찾기 위한 키워드
    keyword = models.CharField(blank=True, default='', max_length=255) #이 카드를 찾기 위한 키워드
    search = models.CharField(blank=True, default='', max_length=255) #이 카드가 찾는 관련 카드 키워드
    
    def __str__(self):
        return self.code + " / " + self.name

    class Meta:
        permissions = [
            ("tag_update", "태그 수정")
        ]

class Tag(models.Model):
    name = models.CharField(max_length=20) #태그명
    description = models.TextField() #태그 설명