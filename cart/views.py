# django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext_lazy as _

# lfs imports
import lfs.cart.utils
import lfs.catalog.utils
import lfs.voucher.utils
import lfs.discounts.utils
from lfs.caching.utils import lfs_get_object_or_404
from lfs.cart.models import CartItemPropertyValue
from lfs.core.signals import cart_changed
from lfs.core import utils as core_utils
from lfs.catalog.models import Product
from lfs.catalog.models import Property
from lfs.catalog.settings import PRODUCT_WITH_VARIANTS
from lfs.cart import utils as cart_utils
from lfs.cart.models import CartItem
from lfs.core.utils import l10n_float
from lfs.shipping import utils as shipping_utils
from lfs.payment import utils as payment_utils
from lfs.customer import utils as customer_utils
from lfs.voucher.models import Voucher
from lfs.voucher.settings import MESSAGES

def cart(request, template_name="lfs/cart/cart.html"):
    """The main view of the cart.
    """
    return render_to_response(template_name, RequestContext(request, {
        "voucher_number" : lfs.voucher.utils.get_current_voucher_number(request),
        "cart_inline" : cart_inline(request),
    }))

def cart_inline(request, template_name="lfs/cart/cart_inline.html"):
    """The actual content of the cart. This is factored out to be reused within
    'normal' and ajax requests.
    """
    cart = cart_utils.get_cart(request)
    shopping_url = lfs.cart.utils.get_go_on_shopping_url(request)
    if cart is None:
        return render_to_string(template_name, RequestContext(request, {
            "shopping_url" : shopping_url,
        }))

    shop = core_utils.get_default_shop()
    countries = shop.countries.all()
    selected_country = shipping_utils.get_selected_shipping_country(request)

    # Get default shipping method, so that we have a one in any case.
    selected_shipping_method = shipping_utils.get_selected_shipping_method(request)
    selected_payment_method = payment_utils.get_selected_payment_method(request)

    shipping_costs = shipping_utils.get_shipping_costs(request,
        selected_shipping_method)

    # Payment
    payment_costs = payment_utils.get_payment_costs(request,
        selected_payment_method)

    # Cart costs
    cart_costs = cart_utils.get_cart_costs(request, cart)
    cart_price = \
        cart_costs["price"] + shipping_costs["price"] + payment_costs["price"]

    cart_tax = \
        cart_costs["tax"] + shipping_costs["tax"] + payment_costs["tax"]

    # Discounts
    discounts = lfs.discounts.utils.get_valid_discounts(request)
    for discount in discounts:
        cart_price = cart_price - discount["price"]

    # Voucher
    voucher_number = lfs.voucher.utils.get_current_voucher_number(request)
    try:
        voucher = Voucher.objects.get(number=voucher_number)
    except Voucher.DoesNotExist:
        display_voucher = False
        voucher_value = 0
        voucher_tax = 0
        voucher_message = MESSAGES[6]
    else:
        lfs.voucher.utils.set_current_voucher_number(request, voucher_number)
        is_voucher_effective, voucher_message = voucher.is_effective(cart)
        if is_voucher_effective:
            display_voucher = True
            voucher_value = voucher.get_price_gross(cart)
            cart_price = cart_price - voucher_value
            voucher_tax = voucher.get_tax(cart)
        else:
            display_voucher = False
            voucher_value = 0
            voucher_tax = 0

    max_delivery_time = cart_utils.get_cart_max_delivery_time(request, cart)

    # Calc delivery date for cart (which is the maximum of all cart items)
    max_delivery_date = cart_utils.get_cart_max_delivery_time(request, cart)

    return render_to_string(template_name, RequestContext(request, {
        "cart" : cart,
        "max_delivery_date" : max_delivery_date,
        "cart_price" : cart_price,
        "cart_tax" : cart_tax,
        "shipping_methods" : shipping_utils.get_valid_shipping_methods(request),
        "selected_shipping_method" : selected_shipping_method,
        "shipping_price" : shipping_costs["price"],
        "payment_methods" : payment_utils.get_valid_payment_methods(request),
        "selected_payment_method" : selected_payment_method,
        "payment_price" : payment_costs["price"],
        "countries" : countries,
        "selected_country" : selected_country,
        "max_delivery_time" : max_delivery_time,
        "shopping_url" : shopping_url,
        "discounts" : discounts,
        "display_voucher" : display_voucher,
        "voucher_number" : voucher_number,
        "voucher_value" : voucher_value,
        "voucher_tax" : voucher_tax,
        "voucher_number" : lfs.voucher.utils.get_current_voucher_number(request),
        "voucher_message" : voucher_message,
    }))

def added_to_cart(request, template_name="lfs/cart/added_to_cart.html"):
    """Shows the product that has been added to the cart.
    """
    cart_items = request.session.get("cart_items", [])
    try:
        accessories = cart_items[0].product.get_accessories()
    except IndexError:
        accessories = []

    return render_to_response(template_name, RequestContext(request, {
        "plural" : len(cart_items) > 1,
        "shopping_url" : request.META.get("HTTP_REFERER", "/"),
        "product_accessories" : accessories,
        "cart_items" : added_to_cart_items(request),
    }))

def added_to_cart_items(request, template_name="lfs/cart/added_to_cart_items.html"):
    """Displays the added items for the added-to-cart view.
    """
    cart_items = request.session.get("cart_items", [])

    total = 0
    for cart_item in cart_items:
        total += (cart_item.get_price() * cart_item.amount)

    return render_to_string(template_name, {
        "total" : total,
        "cart_items" : cart_items,
    })

# Actions
def add_accessory_to_cart(request, product_id, quantity=1):
    """Adds an accessory to the cart and updates the added-to-cart view.
    """
    try:
        quantity = float(quantity)
    except TypeError:
        quantity = 1

    product = lfs_get_object_or_404(Product, pk=product_id)

    session_cart_items = request.session.get("cart_items", [])
    cart = cart_utils.get_cart(request)

    # Add product to cart
    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
    except ObjectDoesNotExist:
        cart_item = CartItem.objects.create(
            cart=cart, product=product, amount=quantity)
        session_cart_items.append(cart_item)
    else:
        cart_item.amount += quantity
        cart_item.save()

        if cart_item not in session_cart_items:
            session_cart_items.append(cart_item)
        else:
            # Update save cart item within session
            for session_cart_item in session_cart_items:
                if cart_item.product == session_cart_item.product:
                    session_cart_item.amount += quantity

    request.session["cart_items"] = session_cart_items

    cart_changed.send(cart, request=request)
    return HttpResponse(added_to_cart_items(request))

def add_to_cart(request, product_id=None):
    """Adds the amount of the product with given id to the cart. If the product
    is already within the cart the amount is increased.
    """
    if product_id is None:
        product_id = request.REQUEST.get("product_id")

    product = lfs_get_object_or_404(Product, pk=product_id)

    # Only active and deliverable products can be added to the cart.
    if (product.is_active() and product.is_deliverable()) == False:
        raise Http404()

    # Validate properties (They are added below)
    properties_dict = {}
    if product.is_configurable_product():
        for key, value in request.POST.items():
            if key.startswith("property-"):
                try:
                    property_id = key.split("-")[1]
                except IndexError:
                    continue
                try:
                    property = Property.objects.get(pk=property_id)
                except Property.DoesNotExist:
                    continue

                if property.is_number_field:
                    value = l10n_float(value)

                properties_dict[property_id] = unicode(value)
                                
                # validate property's value
                if property.is_number_field:

                    if (value < property.unit_min) or (value > property.unit_max):
                        msg = _(u"%(name)s must be between %(min)s and %(max)s %(unit)s.") % {"name" : property.title, "min" : property.unit_min, "max" : property.unit_max, "unit" : property.unit }
                        return lfs.core.utils.set_message_cookie(
                            product.get_absolute_url(), msg)

                    # calculate valid steps
                    steps = []
                    x = property.unit_min
                    while x < property.unit_max:
                        steps.append("%.2f" % x)
                        x = x + property.unit_step
                    steps.append("%.2f" % property.unit_max)

                    value = "%.2f" % value
                    if value not in steps:
                        msg = _(u"Your entered value for %(name)s (%(value)s) is not in valid step width, which is %(step)s.") % {"name": property.title, "value": value, "step" : property.unit_step }
                        return lfs.core.utils.set_message_cookie(
                            product.get_absolute_url(), msg)

    elif product.is_product_with_variants:
        variant_id = request.POST.get("variant_id")
        product = lfs_get_object_or_404(Product, pk=variant_id)

    try:
        quantity = float(request.POST.get("quantity", 1))
    except TypeError:
        quantity = 1

    if product.active_packing_unit:
        quantity = lfs.catalog.utils.calculate_real_amount(product, quantity)

    cart = cart_utils.get_or_create_cart(request)

    # Add properties to cart item
    if product.is_configurable_product():

        # if a product with same properties already exist we increase the
        # amount. Otherwise we create a new one.
        cart_item = cart.get_item(product, properties_dict)
        if cart_item:
            cart_item.amount += quantity
            cart_item.save()
        else:
            cart_item = CartItem(cart=cart, product=product, amount=quantity)
            cart_item.save()

            for property_id, value in properties_dict.items():
                property = Property.objects.get(pk=property_id)

                cpv = CartItemPropertyValue.objects.create(
                    cart_item=cart_item, property_id=property_id, value=value)

    else:
        try:
            cart_item = CartItem.objects.get(cart = cart, product = product)
        except ObjectDoesNotExist:
            cart_item = CartItem(cart=cart, product=product, amount=quantity)
            cart_item.save()
        else:
            cart_item.amount += quantity
            cart_item.save()

    cart_items = [cart_item]

    # Add selected accessories to cart
    for key, value in request.POST.items():
        if key.startswith("accessory"):
            accessory_id = key.split("-")[1]
            try:
                accessory = Product.objects.get(pk=accessory_id)
            except ObjectDoesNotExist:
                continue

            # Get quantity
            quantity = request.POST.get("quantity-%s" % accessory_id, 0)
            try:
                quantity = float(quantity)
            except TypeError:
                quantity = 1

            try:
                cart_item = CartItem.objects.get(cart = cart, product = accessory)
            except ObjectDoesNotExist:
                cart_item = CartItem(cart=cart, product = accessory, amount=quantity)
                cart_item.save()
            else:
                cart_item.amount += quantity
                cart_item.save()

            cart_items.append(cart_item)

    # Store cart items for retrieval within added_to_cart.
    request.session["cart_items"] = cart_items
    cart_changed.send(cart, request=request)

    # Update the customer's shipping method (if appropriate)
    customer = customer_utils.get_or_create_customer(request)
    shipping_utils.update_to_valid_shipping_method(request, customer, save=True)

    # Update the customer's shipping method (if appropriate)
    payment_utils.update_to_valid_payment_method(request, customer, save=True)

    # Save the cart to update modification date
    cart.save()

    try:
        url_name = settings.LFS_AFTER_ADD_TO_CART
    except AttributeError:
        url_name = "lfs.cart.views.added_to_cart"

    return HttpResponseRedirect(reverse(url_name))

def delete_cart_item(request, cart_item_id):
    """Deletes the cart item with the given id.
    """
    lfs_get_object_or_404(CartItem, pk=cart_item_id).delete()

    cart = cart_utils.get_cart(request)
    cart_changed.send(cart, request=request)

    return HttpResponse(cart_inline(request))

def refresh_cart(request):
    """Refreshes the cart after some changes has been taken place: the amount
    of a product or shipping/payment method.
    """
    cart = cart_utils.get_cart(request)
    customer = customer_utils.get_or_create_customer(request)

    # Update country
    country = request.POST.get("country")
    if customer.selected_shipping_address:
        customer.selected_shipping_address.country_id = country
        customer.selected_shipping_address.save()
    if customer.selected_invoice_address:
        customer.selected_invoice_address.country_id = country
        customer.selected_invoice_address.save()
    customer.selected_country_id = country

    # NOTE: The customer has to be saved already here in order to calculate
    # a possible new valid shippig method below, which coulb be triggered by
    # the changing of the shipping country.
    customer.save()

    # Update Amounts
    message = ""
    for item in cart.items():
        amount = request.POST.get("amount-cart-item_%s" % item.id, 0)
        try:
            amount = float(amount)
            if item.product.manage_stock_amount and amount > item.product.stock_amount:
                amount = item.product.stock_amount
                if amount < 0:
                    amount = 0
                message = _(u"Sorry, but there are only %(amount)s article(s) in stock.") % {"amount" : amount}
        except ValueError:
            amount = 1

        if item.product.active_packing_unit:
            item.amount = lfs.catalog.utils.calculate_real_amount(item.product, float(amount))
        else:
            item.amount = amount

        if amount == 0:
            item.delete()
        else:
            item.save()

    # IMPORTANT: We have to send the signal already here, because the valid
    # shipping methods might be dependent on the price.
    cart_changed.send(cart, request=request)

    # Update shipping method
    customer.selected_shipping_method_id = request.POST.get("shipping_method")

    valid_shipping_methods = shipping_utils.get_valid_shipping_methods(request)
    if customer.selected_shipping_method not in valid_shipping_methods:
        customer.selected_shipping_method = shipping_utils.get_default_shipping_method(request)

    # Update payment method
    customer.selected_payment_method_id = request.POST.get("payment_method")

    # Last but not least we save the customer ...
    customer.save()

    result = simplejson.dumps({
        "html" : cart_inline(request),
        "message" : message,
    })

    return HttpResponse(result)

def check_voucher(request):
    """Updates the cart after the voucher number has been changed.
    """
    voucher_number = lfs.voucher.utils.get_current_voucher_number(request)
    lfs.voucher.utils.set_current_voucher_number(request, voucher_number)

    result = simplejson.dumps({
        "html" : (("#cart-inline", cart_inline(request)),)
    })

    return HttpResponse(result)