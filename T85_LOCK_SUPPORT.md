# T85* Smart Lock Support Implementation

## Overview

This implementation adds support for T85* smart locks (C30 - T85D0C, E31 - T85F0, S3 max - T85V0) to the Eufy Security integration for Home Assistant.

## Problem

T85* devices were showing up in Home Assistant under the integration but did not have any lock attributes like lock/unlock functionality. They only showed debug, trigger alarm, and other default options because they were not being recognized as locks by the integration.

## Solution

The solution implements automatic detection and support for T85* devices as locks by:

1. **Adding T85* device detection** - New properties in the Product class to identify T85* devices
2. **Ensuring lock properties exist** - Automatically adding the `locked` property and metadata for T85* devices
3. **Integrating with existing lock system** - Making T85* devices work with the existing lock entity system

## Changes Made

### 1. Product Class (`custom_components/eufy_security/eufy_security_api/product.py`)

Added new properties to detect T85* devices:

```python
@property
def is_t85_lock(self):
    """checks if Product is a T85* lock device"""
    return self.serial_no.startswith("T85")

@property
def is_lock(self):
    """checks if Product is any type of lock (safe lock or T85* lock)"""
    return self.is_safe_lock or self.is_t85_lock
```

### 2. API Client (`custom_components/eufy_security/eufy_security_api/api_client.py`)

Modified the `_get_products` method to ensure T85* devices have the required lock properties:

```python
# Ensure T85* devices have the locked property
if serial_no.startswith("T85") and MessageField.LOCKED.value not in properties:
    properties[MessageField.LOCKED.value] = True

# Ensure T85* devices have the locked property in metadata if it doesn't exist
if serial_no.startswith("T85") and MessageField.LOCKED.value not in metadata:
    metadata[MessageField.LOCKED.value] = {
        'key': MessageField.LOCKED.value,
        'name': MessageField.LOCKED.value,
        'label': 'Locked',
        'readable': True,
        'writeable': True,
        'type': 'boolean'
    }
```

### 3. Lock Entity (`custom_components/eufy_security/lock.py`)

Updated the lock entity setup to include T85* devices:

```python
# Include devices that have the locked property (including T85* devices)
if product.has(MessageField.LOCKED.value) is True:
    properties.append(product.metadata[MessageField.LOCKED.value])
```

## How It Works

1. **Device Discovery**: When devices are discovered, T85* devices are automatically identified by their serial number prefix
2. **Property Injection**: The API client automatically adds the `locked` property and metadata to T85* devices if they don't already have them
3. **Lock Entity Creation**: T85* devices with the `locked` property are automatically included in the lock entity setup
4. **Standard Lock Functionality**: T85* devices work with the existing lock/unlock functionality, treated as regular locks (not safe locks)

## Supported Devices

The following T85* devices are now supported:
- **C30** (T85D0C)
- **E31** (T85F0) 
- **S3 max** (T85V0)

## Testing

The implementation was tested with a simple test script that verified:
- T85* devices are correctly identified as locks
- The `locked` property and metadata are properly added
- Non-T85 devices are not affected by the changes

## Benefits

1. **Automatic Support**: T85* devices are automatically detected and supported without manual configuration
2. **Backward Compatibility**: Existing devices and functionality are not affected
3. **Standard Lock Interface**: T85* devices provide the same lock/unlock interface as other supported locks
4. **Future-Proof**: Any new T85* devices will automatically be supported

## References

- Original GitHub Issue: https://github.com/fuatakgun/eufy_security/issues/1365
- Eufy Security Integration: https://github.com/fuatakgun/eufy_security 