

class PriceCalculator(object):

    def __init__(self, request, product, **kwargs):
        self.request = request
        self.product = product

    def get_standard_price(self, with_properties=True):
        raise NotImplementedError

    def get_price(self, with_properties=True):
        raise NotImplementedError

    def get_for_sale_price(self):
        raise NotImplementedError

    def get_price_gross(self, with_properties=True):
        raise NotImplementedError

    def get_price_with_unit(self):
        raise NotImplementedError

    def calculate_price(self, price):
        raise NotImplementedError

    def get_price_net(self, with_properties=True):
        raise NotImplementedError

    def prices_includes_tax(self):
        raise NotImplementedError

    def get_tax_rate(self):
        raise NotImplementedError

    def get_tax(self):
        raise NotImplementedError