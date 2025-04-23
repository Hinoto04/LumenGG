from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, Http404
from django.db.models import Q, Count


from .forms import UserForm, LoginForm, UserDataForm
from statistic.models import Championship, CSDeck
from deck.models import Deck

def login_view(req):
    redirect_to = req.GET.get('next', 'card:index')
    if redirect_to == '':
        redirect_to = 'card:index'
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

def profile(req, id=0):
    if id==0 and req.user.is_authenticated:
        id = req.user.id
    
    try:
        target = User.objects.get(id=id)
    except User.DoesNotExist:
        raise Http404()
    if req.user == target:
        decks = Deck.objects.filter(author=target)
    else:
        decks = Deck.objects.filter(author=target, private=False)
    decks = decks.annotate(likecount = Count('deck_like')).order_by('-created')
    
    csds = CSDeck.objects.filter(user_model=target)
    
    form = UserDataForm()
    
    context = {
        'target': target,
        'decks': decks,
        'csds': csds,
        'form': form,
    }
    return render(req, 'common/userpage.html', context=context)

def nameToProfile(req, name):
    try:
        target = User.objects.get(username=name)
    except User.DoesNotExist:
        raise Http404()
    
    return profile(req, target.id)

def editProfile(req):
    if req.method == 'POST':
        if req.user.is_authenticated:
            form = UserDataForm(req.POST)
            if form.is_valid():
                req.user.data.character = form.cleaned_data['character']
                req.user.data.save()
            else:
                raise Http404()
            return redirect('common:mypage')
        else:
            raise Http404()
    raise Http404()