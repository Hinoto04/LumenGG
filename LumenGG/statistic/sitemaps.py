from django.contrib import sitemaps
from django.urls import reverse

from .models import Championship

class StaticSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.5

    def items(self):
        return ["stat:index"]

    def location(self, item):
        return reverse(item)

class ChampionshipSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Championship.objects.all()

    def location(self, item):
        return reverse("stat:detail", args=[item.id])