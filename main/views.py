from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


def login_view(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = LoginForm(request, data=request.POST or None)
	if request.method == 'POST' and form.is_valid():
		login(request, form.get_user())
		return redirect('dashboard')

	return render(
		request,
		'main/auth.html',
		{
			'form': form,
			'title': 'Авторизация',
			'subtitle': 'Вход в соревновательную платформу',
			'submit_label': 'Войти',
			'switch_label': 'Нет аккаунта?',
			'switch_url': 'register',
			'switch_text': 'Создать',
		},
	)


def register_view(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = RegisterForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect('dashboard')

	return render(
		request,
		'main/auth.html',
		{
			'form': form,
			'title': 'Регистрация',
			'subtitle': 'Создание профиля без лишних шагов',
			'submit_label': 'Зарегистрироваться',
			'switch_label': 'Уже есть аккаунт?',
			'switch_url': 'login',
			'switch_text': 'Войти',
		},
	)


@login_required
def dashboard_view(request):
	return render(request, 'main/dashboard.html')


def logout_view(request):
	logout(request)
	return redirect('login')
