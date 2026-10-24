from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile
from .topics import TOPIC_CHOICES

class InterestsForm(forms.Form):
    interests=forms.MultipleChoiceField(choices=TOPIC_CHOICES,widget=forms.CheckboxSelectMultiple,required=True)
    learn_from_activity=forms.BooleanField(required=False,initial=True)
    def clean_interests(self):
        values=self.cleaned_data['interests']
        if len(values)>6:
            raise forms.ValidationError('Choose up to six interests. You can change them anytime.')
        return values
def validate_image(image):
    from django.core.files.uploadedfile import UploadedFile
    # An unchanged stored image was validated when uploaded. Reopening it on
    # every edit also leaves unnecessary storage handles alive on Windows.
    if image and not isinstance(image, UploadedFile):
        return image
    if image and hasattr(image, 'size'):
        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Images must be smaller than 5 MB.')
        from PIL import Image, UnidentifiedImageError
        try:
            pic = Image.open(image)
            if pic.format not in ('JPEG', 'PNG', 'WEBP') or pic.width * pic.height > 20000000:
                raise forms.ValidationError('Use a JPEG, PNG or WebP up to 20 megapixels.')
            pic.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise forms.ValidationError('Upload a valid image.')
        finally:
            image.seek(0)
    return image
class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']
    def clean_username(self):
        value = self.cleaned_data['username']
        if User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError('That username is taken.')
        return value
class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['display_name','avatar','bio','location']
    def clean_avatar(self):
        return validate_image(self.cleaned_data.get('avatar'))
