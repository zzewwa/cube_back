from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


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