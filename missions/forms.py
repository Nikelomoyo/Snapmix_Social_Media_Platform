from datetime import timedelta
from django import forms
from django.utils import timezone
from accounts.forms import validate_image
from .models import Mission, Contribution, Discussion


class PrivateImageInput(forms.ClearableFileInput):
    # The default widget asks for FieldFile.url, which private storage forbids.
    # Previews are rendered separately through the authorized mission media view.
    def is_initial(self, value):
        return bool(value and value.name)

    template_name = 'missions/image_input.html'


class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = ['title', 'prompt', 'cover', 'visibility', 'ends_at']
        widgets = {
            'prompt': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Give everyone something to make, find or share…'}),
            'ends_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'cover': PrivateImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        labels = {'ends_at': 'Collection closes at', 'cover': 'Cover photo (optional)'}
        help_texts = {'ends_at': 'South Africa time. Choose a time within the next 30 days.',
                      'visibility': 'Members can pass an invitation to someone else. Invite-only missions stay off public discovery.'}

    def clean_ends_at(self):
        value = self.cleaned_data['ends_at']
        if not timezone.now() + timedelta(minutes=5) < value <= timezone.now() + timedelta(days=30):
            raise forms.ValidationError('Choose a closing time between 5 minutes and 30 days from now.')
        return value

    def clean_cover(self):
        return validate_image(self.cleaned_data.get('cover'))


class ContributionForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ['text', 'image']
        labels = {'text': 'Your perspective', 'image': 'Your photo (optional)'}
        widgets = {'text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Add your part to the story…'}),
                   'image': PrivateImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}

    def clean_image(self):
        return validate_image(self.cleaned_data.get('image'))

    def clean(self):
        data = super().clean()
        if not data.get('text', '').strip() and not data.get('image'):
            raise forms.ValidationError('Add a photo or a few words to contribute.')
        return data


class InviteForm(forms.Form):
    username = forms.CharField(max_length=150, label='Their username', widget=forms.TextInput(attrs={'placeholder': 'e.g. zola', 'autocomplete': 'off'}))


class DiscussionForm(forms.ModelForm):
    class Meta:
        model = Discussion
        fields = ['text']
        labels = {'text': 'Add to the conversation'}
        widgets = {'text': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Swap ideas, encourage someone, make a plan…'})}
