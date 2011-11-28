# django imports
from django import forms
from django.db import models
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

# portlets imports
from portlets.models import Portlet

from lfs.catalog.models import Product
from lfs.caching.utils import lfs_get_object


class ForsalePortlet(Portlet):
    """A portlet for displaying for sale products.
    """

    class Meta:
        app_label = 'portlet'

    name = _("Product Forsale")

    limit = models.IntegerField(_(u"Limit"), default=5)
    current_category = models.BooleanField(_(u"Use current category"), default=False)
    slideshow = models.BooleanField(_(u"Slideshow"), default=False)

    @property
    def rendered_title(self):
        return self.title or self.name

    def render(self, context):
        """Renders the portlet as html.
        """
        request = context.get("request")
        filters = dict(for_sale=True,)
        # filter by current category
        if self.current_category and context.get('category'):
            cat = context.get('category')
            filters['categories__in'] = [cat.id, ]

        products = Product.objects.filter(**filters)[:self.limit]

        return render_to_string("lfs/portlets/forsale.html", RequestContext(request, {
            "title": self.rendered_title,
            "slideshow": self.slideshow,
            "products": products,
            "MEDIA_URL": context.get("MEDIA_URL"),
        }))

    def form(self, **kwargs):
        """
        """
        return ForsaleForm(instance=self, **kwargs)

    def __unicode__(self):
        return "%s" % self.id


class ForsaleForm(forms.ModelForm):
    """
    """
    class Meta:
        model = ForsalePortlet
