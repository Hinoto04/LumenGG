from django.contrib import sitemaps
from django.urls import reverse

from .models import Card

class StaticSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ['card:index', 'card:character']

    def location(self, item):
        return reverse(item)

class CardSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Card.objects.all()

    def location(self, item):
        return reverse("card:detail", args=[item.id])