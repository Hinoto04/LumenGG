from .language import get_language, language_options


def language(request):
    current_language = get_language(request)
    return {
        'current_language': current_language,
        'language_options': language_options(current_language),
    }
