# python imports
from datetime import datetime

# django imports
from django import forms
from django.forms.util import ErrorList
from django.utils.translation import ugettext_lazy as _

# lfs imports
from lfs.payment.settings import CREDIT_CARD_TYPE_CHOICES
from lfs.core.settings import ADDRESS_L10N
from lfs.core.utils import get_default_shop
from lfs.core.models import Country
from lfs.addresses.views import get_l10n 

class OnePageCheckoutForm(forms.Form):
    """
    """
    invoice_firstname = forms.CharField(label=_(u"Firstname"), max_length=50)
    invoice_lastname = forms.CharField(label=_(u"Lastname"), max_length=50)
    invoice_company_name = forms.CharField(label=_(u"Company name"), required=False, max_length=50)
    invoice_street = forms.CharField(label=_(u"Street"), max_length=100)
    invoice_zip_code = forms.CharField(label=_(u"Zip Code"), max_length=10)
    invoice_city = forms.CharField(label=_(u"City"), max_length=50)
    invoice_state = forms.CharField(label=_(u"State"), max_length=50)
    invoice_country = forms.ChoiceField(label=_(u"Country"), required=False)
    invoice_phone = forms.CharField(label=_(u"Phone"), max_length=20)
    invoice_email = forms.EmailField(label=_(u"E-mail"), required=False, max_length=50)
    
    shipping_firstname = forms.CharField(label=_(u"Firstname"), required=False, max_length=50)
    shipping_lastname = forms.CharField(label=_(u"Lastname"), required=False, max_length=50)
    shipping_company_name = forms.CharField(label=_(u"Company name"), required=False, max_length=50)
    shipping_street = forms.CharField(label=_(u"Street"), required=False, max_length=100)
    shipping_zip_code = forms.CharField(label=_(u"Zip Code"), required=False, max_length=10)
    shipping_city = forms.CharField(label=_(u"City"), required=False, max_length=50)
    shipping_state = forms.CharField(label=_(u"State"), required=False, max_length=50)
    shipping_country = forms.ChoiceField(label=_(u"Country"), required=False)
    shipping_phone = forms.CharField(label=_(u"Phone"), required=False, max_length=20)

    account_number = forms.CharField(label=_(u"Account Number"), required=False, max_length=30)
    bank_identification_code = forms.CharField(label=_(u"Bank Indentification Code"), required=False, max_length=30)
    bank_name = forms.CharField(label=_(u"Bankname"), required=False, max_length=100)
    depositor = forms.CharField(label=_(u"Depositor"), required=False, max_length=100)
    
    payment_method = forms.CharField(required=False, max_length=1)
    
    credit_card_type = forms.ChoiceField(label=_(u"Credit Card Type"), choices=CREDIT_CARD_TYPE_CHOICES, required=False)
    credit_card_owner = forms.CharField(label=_(u"Credit Card Owner"), max_length=100, required=False)
    credit_card_number = forms.CharField(label=_(u"Credit Card Number"), max_length=30, required=False)
    credit_card_expiration_date_month = forms.ChoiceField(label=_(u"Expiration Date Month"), required=False)
    credit_card_expiration_date_year = forms.ChoiceField(label=_(u"Expiration Date Year"), required=False)
    credit_card_verification = forms.CharField(label=_(u"Verification Number"), max_length=4, required=False, widget=forms.TextInput(attrs={"size" : 4}))
    
    no_shipping = forms.BooleanField(label=_(u"Same as invoice"), initial=True, required=False)
    message = forms.CharField(label=_(u"Your message to us"), widget=forms.Textarea(attrs={'cols':'80;'}), required=False)

    def __init__(self, *args, **kwargs):
        super(OnePageCheckoutForm, self).__init__(*args, **kwargs)
        
        shop = get_default_shop()
        self.fields["invoice_country"].choices = [(c.id, c.name) for c in shop.countries.all()]
        self.fields["shipping_country"].choices = [(c.id, c.name) for c in shop.countries.all()]
        
        year = datetime.now().year
        self.fields["credit_card_expiration_date_month"].choices = [(i, i) for i in range(1, 13)]
        self.fields["credit_card_expiration_date_year"].choices = [(i, i) for i in range(year, year+10)]
        
        if ADDRESS_L10N:
            # set correct country fields and labels
            initial_data = kwargs.get('initial', None) 
            if  initial_data is not None:
                invoice_country_id = initial_data.get('invoice_country', None)
                if  invoice_country_id is not None:
                    invoice_country = Country.objects.get(id=invoice_country_id)
                    self.set_invoice_fields(invoice_country.code)
                    
                shipping_country_id = initial_data.get('shipping_country', None)
                if  shipping_country_id is not None:
                    shipping_country = Country.objects.get(id=shipping_country_id)
                    self.set_shipping_fields(shipping_country.code)
            
        
    
    def set_invoice_fields(self, country_code):
        l10n_obj = get_l10n(country_code)
        if l10n_obj is not None:
            self.set_fields('invoice', 
                ["_company_name", "_street", "_zip_code", "_city", "_state"], 
                l10n_obj.get_address_fields())
            self.set_fields('invoice', ['_phone'], l10n_obj.get_phone_fields())
            self.set_fields('invoice', ['_email'], l10n_obj.get_email_fields())
        
    def set_shipping_fields(self, country_code):
        l10n_obj = get_l10n(country_code)
        if l10n_obj is not None:
            self.set_fields('shipping', 
                ["_company_name", "_street", "_zip_code", "_city", "_state"], 
                l10n_obj.get_address_fields())
            self.set_fields('shipping', ['_phone'], l10n_obj.get_phone_fields())
            self.set_fields('shipping', ['_email'], l10n_obj.get_email_fields())    
        
    def set_fields(self, prefix, suffixes,  fields):
        assert(len(suffixes) == len(fields))
        i = 0
        for field in fields:
            if field is not None:      
                field_name = prefix+suffixes[i]       
                if self.fields.get(field_name, None) is not None:
                    self.fields[field_name] = field                        
            i = i + 1
        
    def clean(self):
        """
        """
        msg = _(u"This field is required.")
        
        if self.data.get("is_anonymous") == "1" and \
           not self.cleaned_data.get("invoice_email"):
            self._errors["invoice_email"] = ErrorList([msg])

        if not self.cleaned_data.get("no_shipping"):
            if self.cleaned_data.get("shipping_firstname", "") == "":
                self._errors["shipping_firstname"] = ErrorList([msg])

            if self.cleaned_data.get("shipping_lastname", "") == "":
                self._errors["shipping_lastname"] = ErrorList([msg])

            if self.cleaned_data.get("shipping_street", "") == "":
                self._errors["shipping_street"] = ErrorList([msg])

            if self.cleaned_data.get("shipping_zip_code", "") == "":
                self._errors["shipping_zip_code"] = ErrorList([msg])

            if self.cleaned_data.get("shipping_city", "") == "":
                self._errors["shipping_city"] = ErrorList([msg])
                
            if self.cleaned_data.get("shipping_state", "") == "":
                self._errors["shipping_state"] = ErrorList([msg])
                
        # 1 == Direct Debit
        if self.data.get("payment_method") == "1":
            if self.cleaned_data.get("account_number", "") == "":
                self._errors["account_number"] = ErrorList([msg])
            
            if self.cleaned_data.get("bank_identification_code", "") == "":
                self._errors["bank_identification_code"] = ErrorList([msg])

            if self.cleaned_data.get("bank_name", "") == "":
                self._errors["bank_name"] = ErrorList([msg])

            if self.cleaned_data.get("depositor", "") == "":
                self._errors["depositor"] = ErrorList([msg])
        # 6 == Credit Card
        elif self.data.get("payment_method") == "6":
            if self.cleaned_data.get("credit_card_owner", "") == "":
                self._errors["credit_card_owner"] = ErrorList([msg])
            
            if self.cleaned_data.get("credit_card_number", "") == "":
                self._errors["credit_card_number"] = ErrorList([msg])
            
            if self.cleaned_data.get("credit_card_verification", "") == "":
                self._errors["credit_card_verification"] = ErrorList([msg])
        
        return self.cleaned_data