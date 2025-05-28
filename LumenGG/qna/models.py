from django.db import models
from card.models import Card
from martor.models import MartorField

# Create your models here.
class QNA(models.Model):
    title = models.CharField(max_length=100) #제목
    question = models.TextField() #질문
    answer = models.TextField() #답변
    faq = models.BooleanField(default=False) #FAQ 여부
    created_at = models.DateTimeField(auto_now=True) #생성일
    cards = models.ManyToManyField(Card, through='QNARelation', related_name='qna') #관련 카드
    tags = models.CharField(max_length=100, blank=True, default="") #태그
    
    def __str__(self):
        return self.title
    
    class Meta:
        permissions = [
            ("manage", "QNA 관리")
        ]

class QNARelation(models.Model):
    qna = models.ForeignKey(QNA, on_delete=models.CASCADE) #질문
    card = models.ForeignKey(Card, on_delete=models.CASCADE) #관련 카드
    
    def __str__(self):
        return self.qna.title + ' - ' + self.card.name