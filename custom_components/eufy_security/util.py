"""Util functions for integration"""
import logging

from .const import MetadataFilter, PropertyToEntityDescription, DOMAIN, NAME

_LOGGER: logging.Logger = logging.getLogger(__package__)


def get_properties_by_filter(metadata: dict, filtering: MetadataFilter) -> dict:
    """Filter properties based on attributes for presentation"""
    result = {}
    for name, value in metadata.items():
        if (name in PropertyToEntityDescription.__members__) is False:
            continue
        if value.readable is not filtering.readable:
            continue
        if value.writeable is not filtering.writeable:
            continue
        if value.type in filtering.types:
            to_add = False

            if filtering.any_fields is None and filtering.no_fields is None:
                to_add = True
            else:
                if filtering.any_fields is not None:
                    for field in filtering.any_fields:
                        if value.__dict__.get(field, None) is not None:
                            to_add = True
                            break

                if filtering.no_fields is not None:
                    count_no_fields = len(filtering.no_fields)
                    for field in filtering.no_fields:
                        if value.__dict__.get(field, None) is not None:
                            count_no_fields = -1
                            break
                        else:
                            count_no_fields = count_no_fields - 1
                    if count_no_fields == 0:
                        to_add = True
            if to_add is True:
                result[name] = value
    return result


def get_product_properties_by_filter(lists: [], filtering: MetadataFilter):
    """Get product properties entitites list by filter"""
    product_properties = []
    for products in lists:
        for product in products:
            metadatas = get_properties_by_filter(product.metadata, filtering)
            for value in metadatas.values():
                product_properties.append(value)
    return product_properties


def get_device_info(product):
    """generate device info dict"""
    return {
        "identifiers": {(DOMAIN, product.serial_no)},
        "name": product.name,
        "model": product.model,
        "sw_version": product.software_version,
        "manufacturer": NAME,
    }
