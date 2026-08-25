from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, Http404
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Max, Prefetch
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.http import require_GET


from .forms import (
    LoginForm,
    RuleForm,
    RulebookVisualAssetsForm,
    RuleTranslationForm,
    RuleVisualGuideForm,
    RuleVisualGuideTranslationForm,
    UserDataForm,
    UserForm,
)
from .language import LANGUAGE_COOKIE_MAX_AGE, LANGUAGE_COOKIE_NAME, get_language, set_language
from .rulebooks import get_rulebook, ordered_rule_tree, public_rulebook_summaries
from card.models import CharacterComment
from statistic.models import Championship, CSDeck
from deck.models import Deck, CardInDeck
from .models import Rule, Rulebook, RuleTranslation, RuleVisualGuide, UserData

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


@require_GET
def rulebookIndex(req):
    language = get_language(req)
    return render(req, 'common/rulebook_index_v2.html', {
        'rulebooks': public_rulebook_summaries(language),
    })


@require_GET
def rulebookGuide(req):
    return rulebookDetail(req, 'guide')


@require_GET
def rulebookComprehensive(req):
    return rulebookDetail(req, 'comprehensive')


@require_GET
def rulebookTournament(req):
    return rulebookDetail(req, 'tournament')


def rulebookDetail(req, slug):
    language = get_language(req)
    try:
        rulebook = get_rulebook(slug, language)
    except (KeyError, FileNotFoundError):
        raise Http404()
    return render(req, 'common/rulebook_detail_v2.html', {
        'rulebook': rulebook,
        'rulebooks': public_rulebook_summaries(language),
    })


RULE_EDITOR_LANGUAGES = (
    ('ko', '한국어'),
    ('en', 'English'),
    ('ja', '日本語'),
)


def _rule_editor_forms(req, rule=None, initial=None):
    is_post = req.method == 'POST'
    rule_form = RuleForm(
        req.POST if is_post else None,
        instance=rule,
        initial=initial,
    )
    translation_forms = []
    media = rule_form.media
    for language, label in RULE_EDITOR_LANGUAGES:
        instance = None
        if rule and rule.pk:
            instance = rule.translations.filter(language=language).first()
        form = RuleTranslationForm(
            req.POST if is_post else None,
            instance=instance,
            language=language,
            prefix=f'translation-{language}',
        )
        translation_forms.append({
            'language': language,
            'label': label,
            'form': form,
        })
        media += form.media
    return rule_form, translation_forms, media


@permission_required('common.change_rule', raise_exception=True)
@require_GET
def ruleManage(req):
    books = list(
        Rulebook.objects
        .prefetch_related('translations')
        .annotate(
            rule_count=Count('rules', distinct=True),
            root_count=Count('rules', filter=Q(rules__parent__isnull=True), distinct=True),
        )
        .order_by('sort_order', 'id')
    )
    return render(req, 'common/rule_manage_v2.html', {'books': books})


def _rule_title(rule):
    korean = next(
        (item for item in rule.translations.all() if item.language == 'ko'),
        None,
    )
    return korean.title if korean and korean.title else rule.reference_name


def _rule_management_tree(book):
    rules = list(
        Rule.objects
        .filter(rulebook=book)
        .select_related('parent')
        .prefetch_related('translations')
    )
    rows = ordered_rule_tree(rules)
    child_counts = {}
    for rule in rules:
        child_counts[rule.parent_id] = child_counts.get(rule.parent_id, 0) + 1
    for row in rows:
        row['title'] = _rule_title(row['rule'])
        row['child_count'] = child_counts.get(row['rule'].pk, 0)
    return rows


def _mark_move_options(rows):
    for index, row in enumerate(rows):
        row['can_move_up'] = index > 0
        row['can_move_down'] = index < len(rows) - 1
    return rows


def _visual_management_guides(queryset):
    guides = list(queryset.prefetch_related('translations').order_by('priority', 'id'))
    for guide in guides:
        korean = next(
            (item for item in guide.translations.all() if item.language == 'ko'),
            None,
        )
        guide.management_title = (
            korean.title if korean and korean.title else f'비주얼 가이드 {guide.pk}'
        )
    return guides


def _visual_manage_url(guide):
    if guide.rule_id:
        return reverse('rules:manageRule', args=[guide.rule_id])
    return reverse('rules:manageBook', args=[guide.rulebook_id])


def _visual_manage_redirect(guide):
    return redirect(f'{_visual_manage_url(guide)}#visual-{guide.pk}')


def _rule_manage_url(parent_id=None, book_id=None):
    try:
        if parent_id:
            return reverse('rules:manageRule', args=[int(parent_id)])
        if book_id:
            return reverse('rules:manageBook', args=[int(book_id)])
    except (TypeError, ValueError):
        pass
    return reverse('rules:manage')


@permission_required('common.change_rule', raise_exception=True)
@require_GET
def ruleManageBook(req, pk):
    book = get_object_or_404(Rulebook.objects.prefetch_related('translations'), pk=pk)
    root_rows = [row for row in _rule_management_tree(book) if row['rule'].parent_id is None]
    return render(req, 'common/rule_manage_book_v2.html', {
        'book': book,
        'rows': _mark_move_options(root_rows),
        'visual_guides': _visual_management_guides(
            RuleVisualGuide.objects.filter(rulebook=book, rule__isnull=True)
        ),
    })


@permission_required('common.change_rule', raise_exception=True)
@require_GET
def ruleManageRule(req, pk):
    selected = get_object_or_404(Rule.objects.select_related('rulebook'), pk=pk)
    rows = _rule_management_tree(selected.rulebook)
    rows_by_id = {row['rule'].pk: row for row in rows}
    selected_row = rows_by_id[selected.pk]
    child_rows = [row for row in rows if row['rule'].parent_id == selected.pk]

    breadcrumbs = []
    current = selected_row['rule']
    seen = set()
    while current is not None and current.pk not in seen:
        seen.add(current.pk)
        breadcrumbs.append(rows_by_id[current.pk])
        current = rows_by_id.get(current.parent_id, {}).get('rule') if current.parent_id else None
    breadcrumbs.reverse()

    visual_guides = _visual_management_guides(
        RuleVisualGuide.objects
        .filter(rule_id=selected.pk)
    )

    return render(req, 'common/rule_manage_rule_v2.html', {
        'book': selected.rulebook,
        'selected_row': selected_row,
        'rows': _mark_move_options(child_rows),
        'breadcrumbs': breadcrumbs,
        'visual_guides': visual_guides,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_POST
def ruleMove(req, pk, direction):
    if direction not in {'up', 'down'}:
        raise Http404()

    with transaction.atomic():
        selected = get_object_or_404(
            Rule.objects.select_for_update().select_related('rulebook'),
            pk=pk,
        )
        siblings = list(
            Rule.objects
            .select_for_update()
            .filter(rulebook=selected.rulebook, parent_id=selected.parent_id)
            .order_by('priority', 'id')
        )
        selected_index = next(index for index, rule in enumerate(siblings) if rule.pk == selected.pk)
        target_index = selected_index - 1 if direction == 'up' else selected_index + 1
        if 0 <= target_index < len(siblings):
            siblings[selected_index], siblings[target_index] = siblings[target_index], siblings[selected_index]
            for index, rule in enumerate(siblings, start=1):
                rule.priority = index * 10
            Rule.objects.bulk_update(siblings, ['priority'])
            messages.success(req, '규칙 순서를 변경했습니다.')
        else:
            messages.info(req, '더 이상 이동할 수 없습니다.')

    if selected.parent_id:
        return redirect(f'{reverse("rules:manageRule", args=[selected.parent_id])}#rule-{selected.pk}')
    return redirect(f'{reverse("rules:manageBook", args=[selected.rulebook_id])}#rule-{selected.pk}')


def _rule_visual_editor_forms(req, guide=None, initial=None):
    is_post = req.method == 'POST'
    guide_form = RuleVisualGuideForm(
        req.POST if is_post else None,
        instance=guide,
        initial=initial,
    )
    translation_forms = []
    media = guide_form.media
    for language, label in RULE_EDITOR_LANGUAGES:
        instance = None
        if guide and guide.pk:
            instance = guide.translations.filter(language=language).first()
        form = RuleVisualGuideTranslationForm(
            req.POST if is_post else None,
            instance=instance,
            language=language,
            prefix=f'visual-{language}',
        )
        translation_forms.append({
            'language': language,
            'label': label,
            'form': form,
        })
        media += form.media
    return guide_form, translation_forms, media


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleVisualGuideCreate(req, rule_pk):
    rule = get_object_or_404(Rule.objects.select_related('rulebook'), pk=rule_pk)
    next_priority = (
        rule.visual_guides.aggregate(max_priority=Max('priority'))['max_priority'] or 0
    ) + 10
    guide_form, translation_forms, editor_media = _rule_visual_editor_forms(
        req,
        initial={'priority': next_priority, 'is_public': True},
    )
    forms_valid = guide_form.is_valid() if req.method == 'POST' else False
    if req.method == 'POST':
        translations_valid = all(item['form'].is_valid() for item in translation_forms)
        if forms_valid and translations_valid:
            with transaction.atomic():
                guide = guide_form.save(commit=False)
                guide.rulebook = rule.rulebook
                guide.rule = rule
                guide.save()
                for item in translation_forms:
                    item['form'].save_for_guide(guide)
            messages.success(req, '비주얼 가이드를 추가했습니다.')
            return _visual_manage_redirect(guide)
    return render(req, 'common/rule_visual_form_v2.html', {
        'page_title': '비주얼 가이드 추가',
        'rule': rule,
        'book': rule.rulebook,
        'manage_url': reverse('rules:manageRule', args=[rule.pk]),
        'guide': None,
        'guide_form': guide_form,
        'translation_forms': translation_forms,
        'editor_media': editor_media,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def rulebookVisualGuideCreate(req, book_pk):
    book = get_object_or_404(Rulebook, pk=book_pk)
    next_priority = (
        book.visual_guides
        .filter(rule__isnull=True)
        .aggregate(max_priority=Max('priority'))['max_priority']
        or 0
    ) + 10
    guide_form, translation_forms, editor_media = _rule_visual_editor_forms(
        req,
        initial={'priority': next_priority, 'is_public': True},
    )
    forms_valid = guide_form.is_valid() if req.method == 'POST' else False
    if req.method == 'POST':
        translations_valid = all(item['form'].is_valid() for item in translation_forms)
        if forms_valid and translations_valid:
            with transaction.atomic():
                guide = guide_form.save(commit=False)
                guide.rulebook = book
                guide.rule = None
                guide.save()
                for item in translation_forms:
                    item['form'].save_for_guide(guide)
            messages.success(req, '룰북 상단 비주얼 가이드를 추가했습니다.')
            return _visual_manage_redirect(guide)
    return render(req, 'common/rule_visual_form_v2.html', {
        'page_title': '룰북 상단 비주얼 가이드 추가',
        'rule': None,
        'book': book,
        'manage_url': reverse('rules:manageBook', args=[book.pk]),
        'guide': None,
        'guide_form': guide_form,
        'translation_forms': translation_forms,
        'editor_media': editor_media,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def rulebookVisualAssetsEdit(req, book_pk):
    book = get_object_or_404(Rulebook, pk=book_pk)
    form = RulebookVisualAssetsForm(
        req.POST if req.method == 'POST' else None,
        instance=book,
    )
    if req.method == 'POST' and form.is_valid():
        form.save()
        messages.success(req, '룰북 비주얼 공통 코드를 저장했습니다.')
        return redirect('rules:manageBook', pk=book.pk)
    return render(req, 'common/rulebook_visual_assets_form_v2.html', {
        'book': book,
        'form': form,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleVisualGuideEdit(req, pk):
    guide = get_object_or_404(
        RuleVisualGuide.objects.select_related('rule__rulebook', 'rulebook'),
        pk=pk,
    )
    guide_form, translation_forms, editor_media = _rule_visual_editor_forms(req, guide=guide)
    forms_valid = guide_form.is_valid() if req.method == 'POST' else False
    if req.method == 'POST':
        translations_valid = all(item['form'].is_valid() for item in translation_forms)
        if forms_valid and translations_valid:
            with transaction.atomic():
                guide = guide_form.save()
                for item in translation_forms:
                    item['form'].save_for_guide(guide)
            messages.success(req, '비주얼 가이드를 저장했습니다.')
            return _visual_manage_redirect(guide)
    return render(req, 'common/rule_visual_form_v2.html', {
        'page_title': '비주얼 가이드 편집',
        'rule': guide.rule,
        'book': guide.rulebook,
        'manage_url': _visual_manage_url(guide),
        'guide': guide,
        'guide_form': guide_form,
        'translation_forms': translation_forms,
        'editor_media': editor_media,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleVisualGuideDelete(req, pk):
    guide = get_object_or_404(
        RuleVisualGuide.objects.select_related('rule', 'rulebook'),
        pk=pk,
    )
    manage_url = _visual_manage_url(guide)
    if req.method == 'POST':
        guide.delete()
        messages.success(req, '비주얼 가이드를 삭제했습니다.')
        return redirect(manage_url)
    return render(req, 'common/rule_visual_confirm_delete_v2.html', {
        'guide': guide,
        'rule': guide.rule,
        'book': guide.rulebook,
        'manage_url': manage_url,
    })


@permission_required('common.add_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleCreate(req):
    initial = {
        'rulebook': req.GET.get('rulebook') or None,
        'parent': req.GET.get('parent') or None,
    }
    selected_parent_id = req.POST.get('parent') if req.method == 'POST' else initial['parent']
    selected_book_id = req.POST.get('rulebook') if req.method == 'POST' else initial['rulebook']
    manage_url = _rule_manage_url(selected_parent_id, selected_book_id)
    rule_form, translation_forms, editor_media = _rule_editor_forms(req, initial=initial)
    forms_valid = rule_form.is_valid() if req.method == 'POST' else False
    if req.method == 'POST':
        translations_valid = all([item['form'].is_valid() for item in translation_forms])
        if forms_valid and translations_valid:
            with transaction.atomic():
                rule = rule_form.save()
                for item in translation_forms:
                    item['form'].save_for_rule(rule)
            messages.success(req, '규칙을 추가했습니다.')
            if rule.parent_id:
                return redirect(f'{reverse("rules:manageRule", args=[rule.parent_id])}#rule-{rule.pk}')
            return redirect(f'{reverse("rules:manageBook", args=[rule.rulebook_id])}#rule-{rule.pk}')
    return render(req, 'common/rule_form_v2.html', {
        'page_title': '규칙 추가',
        'rule_form': rule_form,
        'translation_forms': translation_forms,
        'editor_media': editor_media,
        'rule': None,
        'manage_url': manage_url,
    })


@permission_required('common.change_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleEdit(req, pk):
    rule = get_object_or_404(Rule.objects.select_related('rulebook'), pk=pk)
    rule_form, translation_forms, editor_media = _rule_editor_forms(req, rule=rule)
    forms_valid = rule_form.is_valid() if req.method == 'POST' else False
    if req.method == 'POST':
        translations_valid = all([item['form'].is_valid() for item in translation_forms])
        if forms_valid and translations_valid:
            with transaction.atomic():
                rule = rule_form.save()
                for item in translation_forms:
                    item['form'].save_for_rule(rule)
            messages.success(req, '규칙을 저장했습니다.')
            return redirect('rules:manageRule', pk=rule.pk)
    return render(req, 'common/rule_form_v2.html', {
        'page_title': '규칙 편집',
        'rule_form': rule_form,
        'translation_forms': translation_forms,
        'editor_media': editor_media,
        'rule': rule,
        'manage_url': reverse('rules:manageRule', args=[rule.pk]),
    })


@permission_required('common.delete_rule', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def ruleDelete(req, pk):
    rule = get_object_or_404(Rule.objects.prefetch_related('translations'), pk=pk)
    if req.method == 'POST':
        parent_id = rule.parent_id
        rulebook_id = rule.rulebook_id
        rule.delete()
        messages.success(req, '규칙과 그 하위 규칙을 삭제했습니다.')
        if parent_id:
            return redirect('rules:manageRule', pk=parent_id)
        return redirect('rules:manageBook', pk=rulebook_id)
    return render(req, 'common/rule_confirm_delete_v2.html', {
        'rule': rule,
        'cancel_url': reverse('rules:manageRule', args=[rule.pk]),
    })
