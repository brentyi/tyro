"""Test adapted from @KolinGuo: https://github.com/brentyi/tyro/issues/156"""

import dataclasses
from typing import Annotated, Optional, Tuple

import tyro


def detect_usb_device(
    vendor_id: Annotated[Optional[str], tyro.conf.arg(aliases=["--vid"])] = None,
    product_id: Annotated[Optional[str], tyro.conf.arg(aliases=["--pid"])] = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect connected USB device by vendor_id + product_id.

    :param vendor_id: vendor_id of a specific USB device.
    :param product_id: product_id of a specific USB device.
    """
    return vendor_id, product_id


def test_detect_usb_device() -> None:
    assert tyro.cli(detect_usb_device, args=["--vid", "0x1234", "--pid", "0x5678"]) == (
        "0x1234",
        "0x5678",
    )
    assert tyro.cli(
        detect_usb_device, args=["--vendor-id", "0x1234", "--product-id", "0x5678"]
    ) == (
        "0x1234",
        "0x5678",
    )
    assert tyro.cli(detect_usb_device, args=[]) == (None, "")


@dataclasses.dataclass
class DeviceStruct:
    vendor_id: Annotated[Optional[str], tyro.conf.arg(aliases=["--vid"])] = None
    product_id: Annotated[Optional[str], tyro.conf.arg(aliases=["--pid"])] = ""


def test_detect_usb_device_dataclass() -> None:
    assert tyro.cli(
        DeviceStruct, args=["--vid", "0x1234", "--pid", "0x5678"]
    ) == DeviceStruct(
        "0x1234",
        "0x5678",
    )
    assert tyro.cli(
        DeviceStruct, args=["--vendor-id", "0x1234", "--product-id", "0x5678"]
    ) == DeviceStruct(
        "0x1234",
        "0x5678",
    )
    assert tyro.cli(DeviceStruct, args=[]) == DeviceStruct(None, "")
