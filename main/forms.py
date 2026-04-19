from io import BytesIO
from pathlib import Path

from django import forms
from django.core.files.base import ContentFile
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps

from .models import UserProfile
from .models import Room
from .profanity import contains_profanity


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Логин',
        widget=forms.TextInput(
            attrs={
                'class': 'auth-input',
                'placeholder': 'Введите логин',
                'autocomplete': 'username',
            }
        ),
    )
    password = forms.CharField(
        label='Пароль',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'auth-input',
                'placeholder': 'Введите пароль',
                'autocomplete': 'current-password',
            }
        ),
    )


class RegisterForm(UserCreationForm):
    password_requirements = (
        'Минимум 8 символов',
        'Хотя бы одна заглавная латинская буква',
        'Хотя бы одна строчная латинская буква',
        'Хотя бы одна цифра',
    )

    username = forms.CharField(
        label='Логин',
        widget=forms.TextInput(
            attrs={
                'class': 'auth-input',
                'placeholder': 'Придумайте логин',
                'autocomplete': 'username',
            }
        ),
    )
    password1 = forms.CharField(
        label='Пароль',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'auth-input',
                'placeholder': 'Введите пароль',
                'autocomplete': 'new-password',
                'data-password-input': 'true',
            }
        ),
    )
    password2 = forms.CharField(
        label='Повтор пароля',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'auth-input',
                'placeholder': 'Повторите пароль',
                'autocomplete': 'new-password',
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if contains_profanity(username):
            raise ValidationError('Логин содержит недопустимые слова. Выберите другой логин.')
        return username

    def clean_password1(self):
        password = self.cleaned_data['password1']

        if len(password) < 8:
            raise ValidationError('Пароль должен содержать минимум 8 символов.')
        if not any(character.isdigit() for character in password):
            raise ValidationError('Пароль должен содержать хотя бы одну цифру.')
        if not any(character.islower() and character.isascii() for character in password):
            raise ValidationError('Пароль должен содержать хотя бы одну строчную латинскую букву.')
        if not any(character.isupper() and character.isascii() for character in password):
            raise ValidationError('Пароль должен содержать хотя бы одну заглавную латинскую букву.')

        return password


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label='Имя', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    email = forms.EmailField(label='Email', required=False)
    avatar_scale = forms.FloatField(required=False, initial=1.0, widget=forms.HiddenInput())
    avatar_offset_x = forms.FloatField(required=False, initial=0.0, widget=forms.HiddenInput())
    avatar_offset_y = forms.FloatField(required=False, initial=0.0, widget=forms.HiddenInput())

    class Meta:
        model = UserProfile
        fields = (
            'display_name',
            'avatar',
            'country',
            'city',
            'telegram',
            'birth_date',
        )
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Как вас показывать в профиле'}),
            'avatar': forms.ClearableFileInput(attrs={'accept': 'image/png,image/jpeg,image/webp,image/gif'}),
            'country': forms.TextInput(attrs={'placeholder': 'Страна'}),
            'city': forms.TextInput(attrs={'placeholder': 'Город'}),
            'telegram': forms.TextInput(attrs={'placeholder': '@username'}),
            'birth_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if self.user is not None:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

        self.fields['birth_date'].input_formats = ['%Y-%m-%d']
        self.fields['birth_date'].localize = False

        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_class} profile-input'.strip()

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if not email:
            return email

        queryset = User.objects.filter(email__iexact=email)
        if self.user is not None:
            queryset = queryset.exclude(pk=self.user.pk)
        if queryset.exists():
            raise ValidationError('Этот email уже используется другим пользователем.')
        return email

    def clean_display_name(self):
        display_name = (self.cleaned_data.get('display_name') or '').strip()
        if not display_name:
            return None

        if contains_profanity(display_name):
            raise ValidationError('Отображаемое имя содержит недопустимые слова. Выберите другое имя.')

        queryset = UserProfile.objects.filter(display_name__iexact=display_name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError('Это отображаемое имя уже занято.')
        return display_name

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar.size > 5 * 1024 * 1024:
            raise ValidationError('Размер аватара не должен превышать 5 МБ.')
        return avatar

    def clean_avatar_scale(self):
        return max(1.0, min(float(self.cleaned_data.get('avatar_scale') or 1.0), 4.0))

    def clean_avatar_offset_x(self):
        return float(self.cleaned_data.get('avatar_offset_x') or 0.0)

    def clean_avatar_offset_y(self):
        return float(self.cleaned_data.get('avatar_offset_y') or 0.0)

    def _process_avatar(self, avatar):
        if not avatar:
            return avatar

        viewport = 280
        scale_multiplier = self.cleaned_data.get('avatar_scale') or 1.0
        offset_x = self.cleaned_data.get('avatar_offset_x') or 0.0
        offset_y = self.cleaned_data.get('avatar_offset_y') or 0.0

        image = Image.open(avatar)
        image = ImageOps.exif_transpose(image)
        has_alpha = image.mode in ('RGBA', 'LA')
        image = image.convert('RGBA' if has_alpha else 'RGB')

        width, height = image.size
        base_scale = max(viewport / width, viewport / height)
        total_scale = base_scale * scale_multiplier
        rendered_width = width * total_scale
        rendered_height = height * total_scale
        left = (viewport - rendered_width) / 2 + offset_x
        top = (viewport - rendered_height) / 2 + offset_y

        crop_left = max(0, min(width - 1, (-left) / total_scale))
        crop_top = max(0, min(height - 1, (-top) / total_scale))
        crop_right = max(crop_left + 1, min(width, (viewport - left) / total_scale))
        crop_bottom = max(crop_top + 1, min(height, (viewport - top) / total_scale))

        cropped = image.crop((crop_left, crop_top, crop_right, crop_bottom)).resize((512, 512), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        extension = '.png' if has_alpha else '.jpg'
        format_name = 'PNG' if has_alpha else 'JPEG'
        save_kwargs = {'format': format_name}
        if format_name == 'JPEG':
            save_kwargs['quality'] = 92
            cropped = cropped.convert('RGB')
        cropped.save(buffer, **save_kwargs)
        buffer.seek(0)

        avatar_name = Path(getattr(avatar, 'name', 'avatar')).stem or 'avatar'
        return ContentFile(buffer.read(), name=f'{avatar_name}_edited{extension}')

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.display_name = self.cleaned_data.get('display_name')

        if self.cleaned_data.get('avatar'):
            profile.avatar = self._process_avatar(self.cleaned_data['avatar'])

        if self.user is not None:
            self.user.first_name = self.cleaned_data['first_name'].strip()
            self.user.last_name = self.cleaned_data['last_name'].strip()
            self.user.email = self.cleaned_data['email'].strip()
            if commit:
                self.user.save(update_fields=['first_name', 'last_name', 'email'])

        if commit:
            profile.save()

        return profile


class RoomCreateForm(forms.ModelForm):
    invite_payload = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Room
        fields = (
            'name',
            'max_players',
            'max_spectators',
            'start_mode',
            'countdown_seconds',
            'study_seconds',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Например: Вечерний турнир'}),
            'start_mode': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['max_players'].min_value = 2
        self.fields['max_players'].max_value = 16
        self.fields['max_spectators'].min_value = 0
        self.fields['max_spectators'].max_value = 64
        self.fields['countdown_seconds'].min_value = 1
        self.fields['countdown_seconds'].max_value = 30
        self.fields['study_seconds'].min_value = 0
        self.fields['study_seconds'].max_value = 120

        for field in self.fields.values():
            classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{classes} profile-input'.strip()
            if isinstance(field.widget, forms.Select):
                select_classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{select_classes} site-select'.strip()

    def clean(self):
        cleaned_data = super().clean()
        max_players = cleaned_data.get('max_players')
        max_spectators = cleaned_data.get('max_spectators')

        if max_players is not None and max_spectators is not None and (max_players + max_spectators) < 2:
            raise ValidationError('Суммарный лимит участников должен быть не меньше 2.')
        return cleaned_data