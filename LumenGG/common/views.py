from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, Http404
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Prefetch
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


from .forms import UserForm, LoginForm, UserDataForm
from .language import LANGUAGE_COOKIE_MAX_AGE, LANGUAGE_COOKIE_NAME, set_language
from card.models import CharacterComment
from statistic.models import Championship, CSDeck
from deck.models import Deck, CardInDeck
from .models import UserData

def login_view(req, template_name='common/login.html', default_redirect='card:index'):
    redirect_to = req.GET.get('next', default_redirect)
    if redirect_to == '':
        redirect_to = default_redirect
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
        return render(req, template_name, context={'form': form})
    else:
        return render(req, template_name, context={'form': LoginForm()})

def loginV2(req):
    return login_view(req, 'common/login_v2.html', 'card:index')

def loginLegacy(req):
    return login_view(req, 'common/login.html', 'card:legacyIndex')

# Create your views here.
@require_POST
def setLanguage(req):
    language = set_language(req, req.POST.get('language'))
    redirect_to = req.POST.get('next') or req.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(
        url=redirect_to,
        allowed_hosts={req.get_host()},
        require_https=req.is_secure(),
    ):
        redirect_to = '/'

    response = redirect(redirect_to)
    response.set_cookie(
        LANGUAGE_COOKIE_NAME,
        language,
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        samesite='Lax',
    )
    return response

@login_required(login_url='common:login')
def logout_view(req):
    logout(req)
    return redirect(req.GET.get('next') or 'card:index')


@login_required(login_url='common:login')
@require_POST
def deleteAccount(req):
    user = req.user

    try:
        with transaction.atomic():
            CharacterComment.objects.filter(author=user).delete()
            user.delete()
    except IntegrityError:
        messages.error(req, '계정 삭제 중 연결된 데이터 제약 조건 문제가 발생했습니다.')
        return redirect('common:mypage')

    logout(req)
    return redirect('card:index')


def signup(req, template_name='common/signup.html', success_route='card:index'):
    if req.method == "POST":
        form = UserForm(req.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(req, user)
            return redirect(success_route)
        else:
            return render(req, template_name, {'form': form})
    else:
        form = UserForm()
        return render(req, template_name, {'form': form})

def signupV2(req):
    return signup(req, 'common/signup_v2.html', 'card:index')

def signupLegacy(req):
    return signup(req, 'common/signup.html', 'card:legacyIndex')

def profile(req, id=0, template_name='common/userpage.html'):
    if id==0 and req.user.is_authenticated:
        id = req.user.id
    
    try:
        target = User.objects.get(id=id)
    except User.DoesNotExist:
        raise Http404()
    if req.user == target:
        decks = Deck.objects.filter(author=target, deleted=False)
    else:
        decks = Deck.objects.filter(author=target, visibility=Deck.VISIBILITY_PUBLIC, deleted=False)
    decks = decks.select_related('author', 'character').annotate(likecount = Count('deck_like', filter=Q(deck_like__like=True))).order_by('-created')
    if template_name == 'common/userpage_v2.html':
        ultimate_cards = CardInDeck.objects.select_related('card').filter(
            card__ultimate=True
        ).order_by('card__name')
        decks = decks.prefetch_related(
            Prefetch('cids', queryset=ultimate_cards, to_attr='ultimate_cards')
        )
    
    csds = CSDeck.objects.filter(user_model=target)
    
    try:
        target_data = target.data
    except UserData.DoesNotExist:
        target_data = None

    form = UserDataForm(instance=target_data)
    
    context = {
        'target': target,
        'decks': decks,
        'csds': csds,
        'form': form,
        'target_data': target_data,
    }
    return render(req, template_name, context=context)

def profileV2(req, id=0):
    return profile(req, id, 'common/userpage_v2.html')

def nameToProfile(req, name):
    try:
        target = User.objects.get(username=name)
    except User.DoesNotExist:
        raise Http404()
    
    return profile(req, target.id)

def nameToProfileV2(req, name):
    try:
        target = User.objects.get(username=name)
    except User.DoesNotExist:
        raise Http404()
    
    return profileV2(req, target.id)

def editProfile(req):
    if req.method == 'POST':
        if req.user.is_authenticated:
            form = UserDataForm(req.POST)
            if form.is_valid():
                try:
                    ud = UserData.objects.get(user=req.user)
                except UserData.DoesNotExist:
                    ud = UserData(
                        user = req.user,
                        character = form.cleaned_data['character']
                        )
                    ud.save()
                else:
                    ud.character = form.cleaned_data['character']
                    ud.save()
            else:
                raise Http404()
            return redirect(req.POST.get('next') or req.META.get('HTTP_REFERER') or 'common:mypage')
        else:
            raise Http404()
    raise Http404()
