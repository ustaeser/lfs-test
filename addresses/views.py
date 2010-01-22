from django.utils.translation import ugettext_lazy as _
from django.forms.widgets import TextInput

from lfs.addresses import library
from lfs.addresses.forms import L10NAddress

NUM_ADDRESS_LINES=5

def get_l10n(country_code):
    l10n_obj = L10NAddress()                
    if library.get(country_code, None) is not None:
        l10n_obj = library.get(country_code)
        assert(len(l10n_obj.get_address_fields()) == NUM_ADDRESS_LINES)
         
    return l10n_obj

