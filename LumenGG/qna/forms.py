from django import forms
from .models import QNA

class QnaSearchForm(forms.Form):
    query = forms.CharField(max_length=255, required=True, label='Search', 
                            widget=forms.TextInput(attrs={'class': 'form-control 배경색1', 'placeholder': '검색'}))

class QnaForm(forms.ModelForm):
    class Meta:
        model = QNA
        fields = ['title', 'question', 'answer', 'faq']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'question': forms.Textarea(attrs={'class': 'form-control'}),
            'answer': forms.Textarea(attrs={'class': 'form-control'}),
        }