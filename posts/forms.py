from django import forms
from accounts.forms import validate_image
from .models import Post, Comment
from accounts.topics import TOPIC_CHOICES
class PostForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['topic'].choices=[('','Suggest from caption')]+TOPIC_CHOICES
    class Meta:
        model = Post
        fields = ['text','image','topic']
        widgets = {'text':forms.Textarea(attrs={'rows':3,'placeholder':"What's your mix today?"})}
    def clean_image(self): return validate_image(self.cleaned_data.get('image'))
    def clean(self):
        data = super().clean()
        if not data.get('text','').strip() and not data.get('image'): raise forms.ValidationError('Add some text or an image.')
        return data
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {'text':forms.Textarea(attrs={'rows':2,'placeholder':'Join the conversation…'})}
