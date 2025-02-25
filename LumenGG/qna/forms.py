from django import forms

class QnaSearchForm(forms.Form):
    query = forms.CharField(max_length=255, required=True, label='Search', 
                            widget=forms.TextInput(attrs={'class': 'form-control 배경색1', 'placeholder': '검색'}))