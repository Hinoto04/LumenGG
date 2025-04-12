from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.http import HttpResponseRedirect
from .forms import UserForm, LoginForm

def login_view(req):
    redirect_to = req.GET.get('next', 'card:index')
    if req.user.is_authenticated:
        return redirect(redirect_to)
    
    if req.method == "POST":
        form = LoginForm(req.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(req, username=username, password=password)
            if user is not None:
                login(req, user)
                return redirect(redirect_to)
        return render(req, 'common/login.html', context={'form': form})
    else:
        return render(req, 'common/login.html')

# Create your views here.
@login_required(login_url='common:login')
def logout_view(req):
    logout(req)
    return redirect('card:index')

def signup(req):
    if req.method == "POST":
        form = UserForm(req.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(req, user)
            return redirect('card:index')
        else:
            return render(req, 'common/signup.html', {'form': form})
    else:
        form = UserForm()
        return render(req, 'common/signup.html', {'form': form})