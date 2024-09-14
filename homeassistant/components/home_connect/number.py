"""Provides number enties for Home Connect."""

import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import ATTR_CONSTRAINTS, ATTR_MAX, ATTR_MIN, ATTR_VALUE, DOMAIN
from .entity import HomeConnectEntity
from .utils import bsh_key_to_translation_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        entities: HomeConnectNumberEntity = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            device = device_dict[CONF_DEVICE]
            entities.extend(
                HomeConnectNumberEntity(device, setting)
                for setting in NUMBER_SETTINGS
                if setting.key in device.appliance.status
            )
        for entity in entities:
            entity.fetch_constraints()
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectNumberEntityDescription(
    NumberEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect binary sensor entity."""


class HomeConnectNumberEntity(HomeConnectEntity, NumberEntity):
    """Number setting class for Home Connect."""

    entity_description: HomeConnectNumberEntityDescription
    bsh_key: str
    _attr_has_entity_name = True

    def __init__(
        self,
        device: HomeConnectDevice,
        entity_description: HomeConnectNumberEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, "")
        self.bsh_key = entity_description.key
        del self._attr_name
        self._attr_unique_id = f"{device.appliance.haId}-{self.bsh_key}"
        self._attr_translation_key = bsh_key_to_translation_key(self.bsh_key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        _LOGGER.debug(
            "Tried to set value %s to %s for %s",
            value,
            self.bsh_key,
            self.entity_id,
        )
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                self.bsh_key,
                value,
            )
        except HomeConnectError as err:
            _LOGGER.error(
                "Error setting value %s to %s for %s: %s",
                value,
                self.bsh_key,
                self.entity_id,
                err,
            )

    def fetch_constraints(self) -> None:
        """Fetch the max and min values and step for the number entity."""
        try:
            data = self.device.appliance.get(f"/status/{self.bsh_key}")
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
            return
        if not data or not (constraints := data.get(ATTR_CONSTRAINTS)):
            return
        self._attr_native_max_value = constraints.get(ATTR_MAX, None)
        self._attr_native_min_value = constraints.get(ATTR_MIN, None)
        self._attr_native_step = 1 if data.get("type", None) == "Int" else 0.1

    async def async_update(self) -> None:
        """Update the number setting status."""
        if not (data := self.device.appliance.status.get(self.bsh_key)):
            _LOGGER.error("No value for %s", self.bsh_key)
            self._attr_native_value = None
            return
        self._attr_native_value = data.get(ATTR_VALUE, None)
        _LOGGER.debug("Updated, new value: %s", self._attr_native_value)

        if (
            not hasattr(self, "_attr_native_min_value")
            or self._attr_native_min_value is None
            or not hasattr(self, "_attr_native_max_value")
            or self._attr_native_max_value is None
            or not hasattr(self, "_attr_native_step")
            or self._attr_native_step is None
        ):
            self.fetch_constraints()


NUMBER_SETTINGS = (
    HomeConnectNumberEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SetpointTemperatureRefrigerator",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SetpointTemperatureFreezer",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.BottleCooler.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.ChillerLeft.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.ChillerCommon.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.ChillerRight.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment2.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectNumberEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment3.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)
