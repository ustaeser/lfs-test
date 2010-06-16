# django imports
from django.contrib.auth.decorators import permission_required
from django.core.paginator import EmptyPage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson
from django.utils.translation import ugettext_lazy as _

# lfs.imports
from lfs.caching.utils import lfs_get_object_or_404
from lfs.catalog.models import Category
from lfs.catalog.models import Product
from lfs.catalog.settings import VARIANT
from lfs.core.signals import featured_changed
from lfs.core.utils import LazyEncoder
from lfs.marketing.models import FeaturedProduct

@permission_required("manage_shop", login_url="/login/")
def manage_featured(
    request, template_name="manage/marketing/featured.html"):
    """
    """
    inline = manage_featured_inline(request, as_string=True)
    
    return render_to_string(template_name, RequestContext(request, {
        "featured_inline" : inline,
    }))

@permission_required("manage_shop", login_url="/login/")
def manage_featured_inline(
    request, as_string=False, template_name="manage/marketing/featured_inline.html"):
    """
    """
    featured = FeaturedProduct.objects.all()
    featured_ids = [f.id for f in featured]
    
    r = request.REQUEST
    s = request.session
    
    # If we get the parameter ``keep-filters`` or ``page`` we take the 
    # filters out of the request resp. session. The request takes precedence.
    # The page parameter is given if the user clicks on the next/previous page 
    # links. The ``keep-filters`` parameters is given is the users adds/removes
    # products. In this way we keeps the current filters when we needed to. If 
    # the whole page is reloaded there is no ``keep-filters`` or ``page`` and 
    # all filters are reset as they should.
    
    if r.get("keep-filters") or r.get("page"):
        page = r.get("page", s.get("featured_products_page", 1))
        filter_ = r.get("filter", s.get("filter"))
        category_filter = r.get("featured_category_filter",
                          s.get("featured_category_filter"))
    else:        
        page = r.get("page", 1)
        filter_ = r.get("filter")
        category_filter = r.get("featured_category_filter")
    
    # The current filters are saved in any case for later use.
    s["featured_products_page"] = page
    s["filter"] = filter_
    s["featured_category_filter"] = category_filter
    
    filters = Q()
    if filter_:
        filters &= Q(name__icontains = filter_)
        filters |= Q(sku__icontains = filter_)
        filters |= (Q(sub_type = VARIANT) & Q(active_sku = False) & Q(parent__sku__icontains = filter_))
        filters |= (Q(sub_type = VARIANT) & Q(active_name = False) & Q(parent__name__icontains = filter_))
        
    if category_filter:
        if category_filter == "None":
            filters &= Q(categories=None)
        else:
            # First we collect all sub categories and using the `in` operator
            category = lfs_get_object_or_404(Category, pk=category_filter)
            categories = [category]
            categories.extend(category.get_all_children())    
            filters &= Q(categories__in = categories)
    
    products = Product.objects.filter(filters).exclude(pk__in = featured_ids)        
    paginator = Paginator(products, 6)
    
    total = products.count()
    try:
        page = paginator.page(page)
    except EmptyPage:
        page = 0
    
    result = render_to_string(template_name, RequestContext(request, {
        "featured" : featured,
        "total" : total,
        "page" : page,
        "paginator" : paginator,
        "filter" : filter_
    }))
    
    if as_string: 
        return result
    else:
        return HttpResponse(result)

# Actions
@permission_required("manage_shop", login_url="/login/")
def add_featured(request):
    """Adds featured by given ids (within request body).
    """
    for temp_id in request.POST.keys():

        if temp_id.startswith("product") == False:
            continue
        
        temp_id = temp_id.split("-")[1]
        FeaturedProduct.objects.create(product_id=temp_id)
            
    inline = manage_featured_inline(request, as_string=True)    
    result = simplejson.dumps({
        "html" : inline,
        "message" : _(u"Featured product has been added.")
    }, cls=LazyEncoder);
    
    return HttpResponse(result)

@permission_required("manage_shop", login_url="/login/") 
def update_featured(request):
    """Saves or removes passed featured product passed id (within request body).
    """
    if request.POST.get("action") == "remove":    
        for temp_id in request.POST.keys():
        
            if temp_id.startswith("product") == False:
                continue
        
            temp_id = temp_id.split("-")[1]
            try:
                featured = FeaturedProduct.objects.get(pk=temp_id)
                featured.delete()
            except (FeaturedProduct.DoesNotExist, ValueError):
                pass
                
            featured_changed.send(featured)

        inline = manage_featured_inline(request, as_string=True)
        result = simplejson.dumps({
            "html" : inline,
            "message" : _(u"Featured product has been removed.")
        }, cls=LazyEncoder);

    else:
        for temp_id in request.POST.keys():
        
            if temp_id.startswith("position") == False:
                continue
                
            temp_id = temp_id.split("-")[1]
            featured = FeaturedProduct.objects.get(pk=temp_id)
                        
            # Update position
            position = request.POST.get("position-%s" % temp_id)
            featured.position = position
            featured.save()
            
        inline = manage_featured_inline(request, as_string=True)
        result = simplejson.dumps({
            "html" : inline,
            "message" : _(u"Featured product has been updated.")
        }, cls=LazyEncoder);
    
    return HttpResponse(result)