# coding=utf8
from django.utils.translation import gettext_lazy as _
from django.conf import settings

ACTION_PLACE_TABS = 1
ACTION_PLACE_FOOTER = 2

ACTION_PLACE_CHOICES = [
    (ACTION_PLACE_TABS, _(u"Tabs")),
    (ACTION_PLACE_FOOTER, _(u"Footer")),
]
POSTAL_ADDRESS_L10N = getattr(settings, 'POSTAL_ADDRESS_L10N', True)

LFS_DEFAULT_PRICE_CALCULATOR = "lfs.gross_price.GrossPriceCalculator"
LFS_PRICE_CALCULATOR_DICTIONARY = {
    'lfs.gross_price.GrossPriceCalculator': 'Price includes tax',
    'lfs.net_price.NetPriceCalculator': 'Price excludes tax',
}

# You can find locale information here: http://en.wikipedia.org/wiki/Locale
LFS_LOCALE = 'de_DE.UTF-8'

# If you use international currency code you will get letters instead of symbols for prices e.g. EUR vs. €
LFS_USE_INTERNATIONAL_CURRENCY_CODE = False