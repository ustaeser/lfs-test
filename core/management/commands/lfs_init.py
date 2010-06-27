# django imports
from django.core.management.base import BaseCommand

SHOP_DESCRIPTION = """
<h1>Welcome to LFS</h1>
<p>LFS is an online shop based on Python, Django and jQuery.</p>
<h1>Login</h1>
<p>Go to the&nbsp;<a href="/manage">management interface</a>&nbsp;to start to add content.</p>
<h1>Information</h1>
<p>You can find more information on following pages:</p>
<ul>
<li><a href="http://www.getlfs.com" target="_blank">Official page</a></li>
<li><a href="http://packages.python.org/django-lfs/index.html" target="_blank">Documentation on PyPI</a></li>
<li><a href="http://bitbucket.org/diefenbach/django-lfs" target="_blank">Source code on bitbucket.org</a></li>
<li><a href="http://twitter.com/lfsproject" target="_blank">Twitter</a></li>
<li><a href="irc://irc.freenode.net/django-lfs" target="_blank">IRC</a></li>
<li><a href="http://groups.google.com/group/django-lfs" target="_blank">Google Group</a></li>
</ul>
"""

class Command(BaseCommand):
    args = ''
    help = 'Initializes LFS'

    def handle(self, *args, **options):
        from lfs.core.models import ActionGroup
        from lfs.core.models import Action
        from lfs.core.models import Country
        from lfs.core.models import Shop

        from portlets.models import Slot
        from portlets.models import PortletAssignment

        from lfs.portlet.models import CartPortlet
        from lfs.portlet.models import CategoriesPortlet
        from lfs.portlet.models import PagesPortlet
        from lfs.payment.models import PaymentMethod
        from lfs.payment.settings import PM_BANK
        from lfs.page.models import Page
        from lfs.shipping.models import ShippingMethod

        # Country
        usa = Country.objects.create(code="us", name="USA")

        # Shop
        shop = Shop.objects.create(name="LFS", shop_owner="John Doe",
            from_email="john@doe.com", notification_emails="john@doe.com", description=SHOP_DESCRIPTION, default_country=usa)
        shop.countries.add(usa)

        # Actions
        tabs = ActionGroup.objects.create(name="Tabs")
        Action.objects.create(group=tabs, title="Contact", link="/contact", active=True, position=1)

        # Portlets
        left_slot = Slot.objects.create(name="Left")
        right_slot = Slot.objects.create(name="Right")

        cart_portlet = CartPortlet.objects.create(title="Cart")
        PortletAssignment.objects.create(slot=right_slot, content=shop, portlet=cart_portlet)

        categories_portlet = CategoriesPortlet.objects.create(title="Categories")
        PortletAssignment.objects.create(slot=left_slot, content=shop, portlet=categories_portlet)

        pages_portlet = PagesPortlet.objects.create(title="Information")
        PortletAssignment.objects.create(slot=left_slot, content=shop, portlet=pages_portlet)

        # Payment methods
        PaymentMethod.objects.create(pk=1, name="Direct debit", priority=1, active=1, deletable=0, type=PM_BANK)
        PaymentMethod.objects.create(pk=2, name="Cash on delivery", priority=2, active=1, deletable=0)
        PaymentMethod.objects.create(pk=3, name="PayPal", priority=3, active=1, deletable=0)
        PaymentMethod.objects.create(pk=4, name="Prepayment", priority=4, active=1, deletable=0)

        # Shipping methods
        ShippingMethod.objects.create(name="Standard", priority=1, active=1)

        # Pages
        Page.objects.create(title="Terms and Conditions", slug="terms-and-conditions", active=1, body="Enter your terms and conditions")