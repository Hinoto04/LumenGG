from django.contrib import sitemaps
from django.urls import reverse

class CollectionSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return ["collection:index"]

    def location(self, item):
        return reverse(item)