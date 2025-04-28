from django.contrib import sitemaps
from django.urls import reverse

class StaticSitemap(sitemaps.Sitemap):
    changefreq = 'daily'
    priority = 0.5

    def items(self):
        return ['battlelog:sim']

    def location(self, item):
        return reverse(item)