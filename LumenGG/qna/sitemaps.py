from django.contrib import sitemaps
from django.urls import reverse

from .models import QNA

class StaticSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ['qna:index']

    def location(self, item):
        return reverse(item)

class QnaSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.5

    def items(self):
        return QNA.objects.all()

    def location(self, item):
        return reverse("qna:detail", args=[item.id])