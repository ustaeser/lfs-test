# django imports
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.file import SessionStore
from django.shortcuts import get_object_or_404
from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse

# test imports
from lfs.catalog.models import Product
from lfs.cart.models import Cart
from lfs.cart.models import CartItem
from lfs.cart.views import add_to_cart
from lfs.cart import utils as cart_utils
from lfs.customer.models import Customer
from lfs.order.utils import add_order
from lfs.order.settings import SUBMITTED
from lfs.payment.models import PaymentMethod
from lfs.shipping.models import ShippingMethod
from lfs.tax.models import Tax
from lfs.core.models import Shop
from lfs.order.models import Order
from lfs.payment.settings import BY_INVOICE, DIRECT_DEBIT


# 3rd party imports
from countries.models import Country
from postal.models import PostalAddress

class CheckoutTestCase(TestCase):
    """
    """
    
    def setUp(self):
        """
        """
        ie = Country.objects.get(iso="IE")
        gb = Country.objects.get(iso="GB")
        de = Country.objects.get(iso="DE")
        us = Country.objects.get(iso="US")
        fr = Country.objects.get(iso="FR")

        shop, created = Shop.objects.get_or_create(name="lfs test", shop_owner="John Doe",
                                          default_country=us)
        shop.save()
        shop.invoice_countries.add(ie)
        shop.invoice_countries.add(gb)
        shop.invoice_countries.add(de)
        shop.invoice_countries.add(us)
        shop.invoice_countries.add(fr)
        shop.shipping_countries.add(ie)
        shop.shipping_countries.add(gb)
        shop.shipping_countries.add(de)
        shop.shipping_countries.add(us)
        shop.shipping_countries.add(fr)
        shop.save()

        tax = Tax.objects.create(rate = 19)
        
        shipping_method = ShippingMethod.objects.create(
            name="Standard",
            active=True,
            price=1.0,
            tax=tax
        )

        direct_debit = PaymentMethod.objects.create(
            name="Direct Debit",
            active=True,
            tax=tax,
        )

        cod = PaymentMethod.objects.create(
            name="Cash on delivery",
            active=True,
            tax=tax,
        )

        paypal = PaymentMethod.objects.create(
            name="PayPal",
            active=True,
            tax=tax,
        )

        prepayment = PaymentMethod.objects.create(
            name="Prepayment",
            active=True,
            tax=tax,
        )

        by_invoice = PaymentMethod.objects.create(
            name="By invoice",
            active=True,
            tax=tax,
        )
        
        
        address1 = PostalAddress.objects.create(
            firstname = "John",
            lastname = "Doe",
            line1 = "Doe Ltd.",
            line2 = "Street 42",
            line3 = "2342",
            line4 = "Gotham City",
            country = gb,
        )

        address2 = PostalAddress.objects.create(
            firstname = "Jane",
            lastname = "Doe",
            line1 = "Doe Ltd.",
            line2 = "Street 43",
            line3 = "2443",
            line4 = "Smallville",
            country = fr,
        )
        
        self.username = 'joe'
        self.password = 'bloggs'
    
        new_user = User(username=self.username)
        new_user.set_password(self.password)
        new_user.save()
        
        self.customer = Customer.objects.create(
            user = new_user,
            selected_shipping_method = shipping_method,
            selected_payment_method = by_invoice,
            selected_shipping_address = address1,
            selected_invoice_address = address2,            
        )
        
        self.PRODUCT1_NAME="Surfboard"
        p1 = Product.objects.create(
            name=self.PRODUCT1_NAME,
            slug="product-1",
            sku="sku-1",
            price=1.1,
            tax = tax,
        )
            
        p2 = Product.objects.create(
            name="Product 2",
            slug="product-2",
            sku="sku-2",
            price=2.2,
            tax = tax,
        )
        
        cart = Cart.objects.create(
            user=new_user
        )
        
        item = CartItem.objects.create(
            cart = cart,
            product = p1,
            amount = 2,
        )

        item = CartItem.objects.create(
            cart = cart,
            product = p2,
            amount = 3,
        )
        
        self.c = Client()

    def dump_response(self, http_response):
        fo = open('tests_checkout.html', 'w')
        fo.write(str(http_response))
        fo.close()
        
    def test_checkout_page(self):
        """Tests that checkout page gets populated with correct details
        """
        # login as our customer
        logged_in = self.c.login(username=self.username, password=self.password)
        self.assertEqual(logged_in, True)

        cart_response = self.c.get(reverse('lfs_cart'))
        self.assertContains(cart_response, self.PRODUCT1_NAME, status_code=200)        
        
        checkout_response = self.c.get(reverse('lfs_checkout'))
        self.assertContains(checkout_response, 'Smallville', status_code=200)

    def test_order_phone_email_set_after_checkout(self):
        # login as our customer
        logged_in = self.c.login(username=self.username, password=self.password)
        self.assertEqual(logged_in, True)

        # check initial database quantities
        self.assertEquals(PostalAddress.objects.count(), 2)
        self.assertEquals(Customer.objects.count(), 1)
        self.assertEquals(Order.objects.count(), 0)

        # check we have no invoice or shipping phone or email prior to checkout
        our_customer = Customer.objects.all()[0]
        self.assertEqual(our_customer.selected_invoice_phone, '')
        self.assertEqual(our_customer.selected_invoice_email, None)
        self.assertEqual(our_customer.selected_shipping_phone, '')
        self.assertEqual(our_customer.selected_shipping_email, None)

        checkout_data = {'invoice-firstname':'bob',
                         'invoice-lastname':'builder',
                         'invoice-line1': 'de company',
                         'invoice-line2': 'de street',
                         'invoice-line3': 'de area',
                         'invoice-line4': 'de town',
                         'invoice-line5': 'cork',
                         'invoice-country':"IE",
                         'invoice_email': 'a@a.com',
                         'invoice_phone': '1234567',
                         'shipping-firstname':'hans',
                         'shipping-lastname':'schmidt',
                         'shipping-line1': 'orianenberger strasse',
                         'shipping-line2': 'de town',
                         'shipping-line3': 'stuff',
                         'shipping-line4': 'BE',
                         'shipping-line5': '12345',
                         'shipping-country':"DE",
                         'payment_method': BY_INVOICE,
                         'shipping_email': 'b@b.com',
                         'shipping_phone': '7654321',
                         }

        checkout_post_response = self.c.post(reverse('lfs_checkout'), checkout_data)
        self.assertRedirects(checkout_post_response, reverse('lfs_thank_you'), status_code=302, target_status_code=200,)

        # check database quantities post-checkout
        self.assertEquals(PostalAddress.objects.count(), 2)
        self.assertEquals(Customer.objects.count(), 1)
        self.assertEquals(Order.objects.count(), 1)

        # check our customer details post checkout
        our_customer = Customer.objects.all()[0]
        self.assertEqual(our_customer.selected_invoice_phone, "1234567")
        self.assertEqual(our_customer.selected_invoice_email, "a@a.com")
        self.assertEqual(our_customer.selected_shipping_phone, '7654321')
        self.assertEqual(our_customer.selected_shipping_email, "b@b.com")
