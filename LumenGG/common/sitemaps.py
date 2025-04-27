from django.contrib import sitemaps
from django.urls import reverse

from django.contrib.auth.models import User

class StaticSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ['common:login', 'common:signup']

    def location(self, item):
        return reverse(item)

class UserSitemap(sitemaps.Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return User.objects.all()

    def location(self, item):
        return reverse("common:userpage", args=[item.id])