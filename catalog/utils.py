import locale

# django imports
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.core.exceptions import FieldError
from django.db.models import Q, Count, Min, Max

# import lfs
import lfs.catalog.models
from lfs.catalog.settings import CONFIGURABLE_PRODUCT
from lfs.catalog.settings import STANDARD_PRODUCT
from lfs.catalog.settings import PRODUCT_WITH_VARIANTS
from lfs.catalog.settings import PROPERTY_VALUE_TYPE_FILTER

# Load logger
import logging
from lfs.manufacturer.models import Manufacturer

logger = logging.getLogger("default")


# TODO: Add unit test
def get_current_top_category(request, obj):
    """
    Returns the current top category of a product.
    """
    if obj.__class__.__name__.lower() == "product":
        category = obj.get_current_category(request)
    else:
        category = obj

    if category is None:
        return category

    while category.parent is not None:
        category = category.parent

    return category


def get_price_filters(category, product_filter, price_filter, manufacturer_filter):
    """ Creates price filter based on the min and max prices of the category's
        products
    """
    # If a price filter is set we return just this.
    if price_filter:
        return {
            "show_reset": True,
            "min": locale.format("%.2f", price_filter["min"]),
            "max": locale.format("%.2f", price_filter["max"]),
            "disabled": False,
        }

    # Base are the filtered products
    products = get_filtered_products_for_category(category, product_filter, price_filter, None, manufacturer_filter)
    if not products:
        return []

    all_products = lfs.catalog.models.Product.objects.filter(Q(pk__in=products) | (Q(parent__in=products) & Q(active=True)))
    res = all_products.aggregate(min_price=Min('effective_price'), max_price=Max('effective_price'))

    pmin, pmax = res['min_price'], res['max_price']

    disabled = (pmin and pmax) is None

    try:
        pmin = locale.format("%.2f", pmin)
    except TypeError:
        pmin = 0.0
    try:
        pmax = locale.format("%.2f", pmax)
    except TypeError:
        pmax = 0.0

    return {
        "show_reset": False,
        "min": pmin,
        "max": pmax,
        "disabled": disabled,
    }


def get_manufacturer_filters(category, product_filter, price_filter, manufacturer_filter):
    """Creates manufacturer filter links based on the manufacturers bound to the products in category
    """
    # Base are the filtered products
    products = get_filtered_products_for_category(category, product_filter, price_filter, None, None)
    if not products:
        return []

    all_products = lfs.catalog.models.Product.objects.filter(Q(pk__in=products) | (Q(parent__in=products) & Q(active=True)))

    # And their parents
    # product_ids = []
    # for product in products:
    #     if product.parent:
    #         product_ids.append(product.parent_id)
    #     else:
    #         product_ids.append(product.pk)

    out = {"show_reset": False}
    if manufacturer_filter:
        out = {
            "show_reset": True
        }
    else:
        manufacturer_filter = []

    qs = Manufacturer.objects.filter(products__in=all_products).annotate(products_count=Count('products'))
    out['items'] = [{'obj': obj, 'selected': obj.pk in manufacturer_filter} for obj in qs]
    return out


def get_product_filters(category, product_filter, price_filter, manufacturer_filter, sorting):
    """Returns the next product filters based on products which are in the given
    category and within the result set of the current filters.
    """
    properties_mapping = get_property_mapping()
    options_mapping = get_option_mapping()
    property_ids = _get_property_ids()
    product_ids = _get_product_ids(category)
    set_filters = dict(product_filter)

    ########## Number Fields ###################################################
    number_fields = []
    cursor = connection.cursor()
    cursor.execute("""SELECT property_id, min(value_as_float), max(value_as_float)
                      FROM catalog_productpropertyvalue
                      WHERE type=%s
                      AND product_id IN (%s)
                      AND property_id IN (%s)
                      GROUP BY property_id""" % (PROPERTY_VALUE_TYPE_FILTER, product_ids, property_ids))
    for row in cursor.fetchall():
        prop = properties_mapping[row[0]]

        if prop.is_select_field or prop.is_text_field or not prop.filterable:
            continue
        if product_filter.get("number-filter", {}).get(str(prop.id)):
            pmin, pmax = product_filter.get("number-filter").get(str(prop.id))[0:2]
            show_reset = True
        else:
            pmin, pmax = row[1:3]
            show_reset = False

        try:
            pmin = locale.format("%.2f", float(pmin))
        except TypeError:
            pmin = 0.0
        try:
            pmax = locale.format("%.2f", float(pmax))
        except TypeError:
            pmax = 0.0

        number_fields.append({
            "id": row[0],
            "position": prop.position,
            "object": prop,
            "name": prop.name,
            "title": prop.title,
            "unit": prop.unit,
            "show_reset": show_reset,
            "show_quantity": True,
            "items": {"min": pmin, "max": pmax},
        })

    ########## Select Fields & Text Fields #####################################
    result = []
    cursor = connection.cursor()
    cursor.execute("""SELECT property_id, value
                      FROM catalog_productpropertyvalue
                      WHERE type=%s
                      AND product_id IN (%s)
                      AND property_id IN (%s)
                      GROUP BY property_id, value""" % (PROPERTY_VALUE_TYPE_FILTER, product_ids, property_ids))

    properties = {}
    for row in cursor.fetchall():
        prop = properties_mapping[row[0]]

        if prop.is_number_field or not prop.filterable:
            continue

        if prop.is_select_field:
            name = options_mapping[row[1]].name
            position = options_mapping[row[1]].position
        else:
            name = row[1]
            position = 10

        if name == row[1] and name == '':
            continue

        if row[0] not in properties:
            properties[row[0]] = []
        properties[row[0]].append({
            "id": row[0],
            "value": row[1],
            "name": name,
            "title": prop.title,
            "position": position,
            "show_quantity": True,
        })

    # Creates the filters to count the existing products per property option,
    # which is used within the filter portlet
    new_product_filter = {}
    if product_filter.get("number-filter"):
        new_product_filter["number-filter"] = product_filter["number-filter"]

    for prop, options in properties.items():
        for option in options:
            # The option in question is used at any rate
            new_product_filter["select-filter"] = {str(prop): option["value"]}

            # All checked options of all other properties is also used
            for f0, f1 in product_filter.get("select-filter", {}).items():
                if f0 != str(prop):
                    new_product_filter["select-filter"][f0] = f1

                # Tests if the option is checked
                if (f0 == str(prop)) and (option["value"] in f1.split("|")):
                    option["checked"] = True

            option["quantity"] = len(get_filtered_products_for_category(category, new_product_filter, price_filter, None))

    # Transform the group properties into a list of dicts
    for property_id, items in properties.items():
        prop = properties_mapping[property_id]
        items.sort(lambda a, b: cmp(a["position"], b["position"]))

        # Move items with zero quantity to the end of the list
        for x in range(0, len(items)):
            if items[x]["quantity"] == 0:
                items.insert(len(items), items.pop(x))

        result.append({
            "id": property_id,
            "position": prop.position,
            "unit": prop.unit,
            "show_reset": str(property_id) in set_filters.get('select-filter', {}).keys(),
            "name": prop.name,
            "title": prop.title,
            "items": items,
        })

    result.sort(lambda a, b: cmp(a["position"], b["position"]))

    return {
        "select_fields": result,
        "number_fields": number_fields,
    }

def _get_property_ids():
    property_ids = lfs.catalog.models.ProductPropertyValue.objects.distinct().values_list('property_id', flat=True)
    return ", ".join(map(str, property_ids))


def _get_product_ids(category):
    products = category.get_all_products()
    if not products:
        return ''

    all_products = lfs.catalog.models.Product.objects.filter(Q(pk__in=products) | (Q(parent__in=products) & Q(active=True)))
    product_ids = all_products.values_list('id', flat=True)

    return ", ".join(map(str, product_ids))


# TODO: Implement this as a method of Category
def get_filtered_products_for_category(category, filters, price_filter, sorting, manufacturers_filter=None):
    """Returns products for given categories and current filters sorted by
    current sorting.
    """
    from lfs.catalog.models import Product, ProductPropertyValue
    if filters:
        if category.show_all_products:
            products = category.get_all_products()
        else:
            products = category.get_products()

        # All variants of category products
        all_variants = Product.objects.filter(parent__in=products)

        # Generate filter
        filters_query = Q()
        for prop, value in filters.get("select-filter", {}).items():
            if value.find("|") == -1:
                q = Q(property_id=prop, value=value)
            else:
                options = []
                q_options = Q()
                for option in value.split("|"):
                    q_options |= Q(value=option)
                q = Q(property_id=prop) & q_options
            filters_query |= q

        for prop, values in filters.get("number-filter", {}).items():
            q = Q(property_id=prop, value_as_float__range=(values[0], values[1]))
            filters_query |= q

        # The idea behind SQL query generated below is: If for every filter (property=value) for a product id exists
        # a "product property value" the product matches.
        #
        # Example ValuesListQuerySet built by statements below is:
        #
        # ProductPropertyValue.objects.filter(Q(property_id=1, value='1') | Q(property_id=2, value='1'),
        #                                     product__in=products,
        #                                     type=PROPERTY_VALUE_TYPE_FILTER) \
        #                             .values('product_id') \
        #                             .annotate(cnt=Count('id')).filter(cnt=2).values_list('product_id', flat=True)
        #
        # it evaluates to:
        #
        # SELECT "catalog_productpropertyvalue"."product_id"
        #   FROM "catalog_productpropertyvalue"
        #  WHERE ((
        #          ("catalog_productpropertyvalue"."value" = 1  AND "catalog_productpropertyvalue"."property_id" = 1 )
        #          OR
        #          ("catalog_productpropertyvalue"."value" = 1  AND "catalog_productpropertyvalue"."property_id" = 2 )
        #        )
        #    AND "catalog_productpropertyvalue"."type" = 0
        #    AND "catalog_productpropertyvalue"."product_id" IN (SELECT U0."id"
        #                                                          FROM "catalog_product" U0
        #                                                         WHERE U0."name" LIKE %da% ESCAPE '\' ))
        #  GROUP BY "catalog_productpropertyvalue"."product_id"
        # HAVING COUNT("catalog_productpropertyvalue"."id") = 2

        length = len(filters.get("select-filter", {}).items()) + len(filters.get("number-filter", {}).items())

        # PRODUCTS - get all products with matching filters.
        matching_product_ids = ProductPropertyValue.objects.filter(product__in=products,
                                                                   type=PROPERTY_VALUE_TYPE_FILTER)
        if filters_query is not None:
            matching_product_ids = matching_product_ids.filter(filters_query)
        matching_product_ids = matching_product_ids.values('product_id').annotate(cnt=Count('id')) \
                                                   .filter(cnt=length).values_list('product_id', flat=True)

        # VARIANTS - get matching variants and then their parents as we're interested in products with variants,
        # not variants itself
        matching_variant_ids = ProductPropertyValue.objects.filter(product__in=all_variants,
                                                                   type=PROPERTY_VALUE_TYPE_FILTER)
        if filters_query is not None:
            matching_variant_ids = matching_variant_ids.filter(filters_query)
        matching_variant_ids = matching_variant_ids.values('product_id').annotate(cnt=Count('id')) \
                                                   .filter(cnt=length).values_list('product_id', flat=True)
        variant_products = Product.objects.filter(pk__in=matching_variant_ids)

        # Merge results
        products = Product.objects.filter(Q(pk__in=matching_product_ids) |
                                          Q(pk__in=variant_products.values_list('parent_id', flat=True))).distinct()
    else:
        categories = [category]
        if category.show_all_products:
            categories.extend(category.get_all_children())
        products = lfs.catalog.models.Product.objects.filter(
            active=True,
            categories__in=categories,
            sub_type__in=[STANDARD_PRODUCT, PRODUCT_WITH_VARIANTS, CONFIGURABLE_PRODUCT]).distinct()

    # TODO: It might be more effective to move price filters directly into if/else clause above
    if price_filter:
        # Get all variants of the products
        variants = lfs.catalog.models.Product.objects.filter(parent__in=products, active=True)
        # Filter the variants by price
        variants = variants.filter(effective_price__range=[price_filter["min"],
                                                           price_filter["max"]])
        # Filter the products
        filtered_products = products.filter(effective_price__range=[price_filter["min"],
                                                                    price_filter["max"]], active=True)
        # merge the result and get a new query set of all products
        # We get the parent ids of the variants as the "product with variants"
        # should be displayed and not the variants.
        products = lfs.catalog.models.Product.objects.filter(
            Q(pk__in=filtered_products) | Q(pk__in=variants.values_list('parent_id', flat=True)))

    if manufacturers_filter:
        # Get all variants of the products
        variants = lfs.catalog.models.Product.objects.filter(parent__in=products)
        # Filter the variants by manufacturer
        variants = variants.filter(manufacturer__in=manufacturers_filter)
        # Filter the products
        filtered_products = products.filter(manufacturer__in=manufacturers_filter)

        # merge the result and get a new query set of all products
        # We get the parent ids of the variants as the "product with variants"
        # should be displayed and not the variants.
        products = lfs.catalog.models.Product.objects.filter(
            Q(pk__in=filtered_products) | Q(pk__in=variants.values_list('parent_id', flat=True)))

    if sorting:
        try:
            products = products.order_by(sorting)
        except FieldError:
            # ignore invalid sort order which may be stored in the session
            pass

    return products


def get_option_mapping():
    """Returns a dictionary with option id to property name.
    """
    options = {}
    for option in lfs.catalog.models.PropertyOption.objects.all():
        options[str(option.id)] = option
    return options


def get_property_mapping():
    """Returns a dictionary with property id to property name.
    """
    properties = {}
    for property in lfs.catalog.models.Property.objects.all():
        properties[property.id] = property

    return properties


def _calculate_steps(product_ids, property, min, max):
    """Calculates filter steps.

    **Parameters**

    product_ids
        The product_ids for which the steps are calculated. List of ids.

    property
        The property for which the steps are calculated. Instance of Property.

    min / max
        The min and max value of all steps. Must be a Float.

    """
    try:
        min = float(min)
        max = float(max)
    except TypeError:
        return []

    result = []

    filter_steps = lfs.catalog.models.FilterStep.objects.filter(property=property.id)
    if property.is_steps_step_type:
        for i, step in enumerate(filter_steps[:len(filter_steps) - 1]):
            min = step.start
            if i != 0:
                min += 1.0
            max = filter_steps[i + 1].start

            result.append({
                "min": min,
                "max": max,
                "quantity": _calculate_quantity(product_ids, property.id, min, max)
            })
    else:
        if property.is_automatic_step_type:
            if max == min:
                step = max
            else:
                diff = max - min
                step = diff / 3         # TODO: Should this be variable?

            if step >= 0 and step < 2:
                step = 1
            elif step >= 2 and step < 6:
                step = 5
            elif step >= 6 and step < 11:
                step = 10
            elif step >= 11 and step < 51:
                step = 50
            elif step >= 51 and step < 101:
                step = 100
            elif step >= 101 and step < 501:
                step = 500
            elif step >= 501 and step < 1001:
                step = 1000
            elif step >= 1000 and step < 5001:
                step = 500
            elif step >= 5001 and step < 10001:
                step = 1000
        else:
            step = property.step

        for n, i in enumerate(range(0, int(max), step)):
            if i > max:
                break
            min = i + 1
            max = i + step

            result.append({
                "min": min,
                "max": max,
                "quantity": _calculate_quantity(product_ids, property.id, min, max),
            })

    if property.display_no_results:
        return result
    else:
        # Remove entries with zero products
        new_result = []
        for n, f in enumerate(result):
            if f["quantity"] == 0:
                try:
                    result[n + 1]["min"] = f["min"]
                except IndexError:
                    pass
                continue
            new_result.append(f)

        return new_result


def _calculate_quantity(product_ids, property_id, min, max):
    """Calculate the amount of products for given parameters.
    """
    # Count entries for current filter
    cursor = connection.cursor()
    cursor.execute("""SELECT property_id, value, parent_id
                      FROM catalog_productpropertyvalue
                      WHERE product_id IN (%s)
                      AND property_id = %s
                      AND value_as_float BETWEEN %s AND %s""" % (product_ids, property_id, min, max))

    already_count = {}
    amount = 0
    for row in cursor.fetchall():
        # We count a property/value pair just one time per *product*. For
        # "products with variants" this could be stored several times within the
        # catalog_productpropertyvalue. Imagine a variant with two properties
        # color and size:
        #   v1 = color:red / size: s
        #   v2 = color:red / size: l
        # But we want to count color:red just one time. As the product with
        # variants is displayed at not the variants.

        if "%s%s%s" % (row[2], row[0], row[1]) in already_count:
            continue
        already_count["%s%s%s" % (row[2], row[0], row[1])] = 1

        amount += 1

    return amount
