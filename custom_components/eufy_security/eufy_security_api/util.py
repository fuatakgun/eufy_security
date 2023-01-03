"""Util functions for integration"""
import asyncio
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)


def get_child_value(data, path, default_value=None):
    """Extract values from mutli level dictionaries based on path"""
    value = data
    for key in path.split("."):
        try:
            value = value[key]
        except:  # pylint: disable=bare-except
            try:
                value = value[int(key)]
            except:  # pylint: disable=bare-except
                value = default_value
    return value


async def wait_for_value(ref_dict: dict, ref_key: str, value, max_iteration: int = 50, interval=0.25):
    """wait for value to be different than initial value"""
    _LOGGER.debug(f"wait start - {ref_key}")
    for _ in range(max_iteration):
        if ref_dict.get(ref_key, value) == value:
            await asyncio.sleep(interval)
        else:
            _LOGGER.debug(f"wait finish - {ref_key} - return True")
            return True
    _LOGGER.debug(f"wait finish - {ref_key} - return False")
    return False


async def wait_for_value_to_equal(ref_dict: dict, ref_key: str, value, max_iteration: int = 50, interval=0.25):
    """wait for value to be different than initial value"""
    _LOGGER.debug(f"wait start - {ref_key}")
    for _ in range(max_iteration):
        if ref_dict.get(ref_key, None) == value:
            _LOGGER.debug(f"wait finish - {ref_key} - return True")
            return True
        else:
            await asyncio.sleep(interval)
    _LOGGER.debug(f"wait finish - {ref_key} - return False")
    return False
