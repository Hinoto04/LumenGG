from django.contrib import sitemaps
from django.urls import reverse

from .models import Deck

class StaticSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ['deck:index']

    def location(self, item):
        return reverse(item)

class DeckSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Deck.objects.filter(private=False, deleted=False)

    def location(self, item):
        return reverse("deck:detail", args=[item.id])