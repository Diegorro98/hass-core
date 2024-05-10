"""Stellantis time platform."""

from datetime import datetime, time

from jsonpath import jsonpath

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomeAssistantStellantisData
from .api import StellantisVehicle
from .const import ATTR_START, DOMAIN
from .coordinator import StellantisUpdateCoordinator
from .entity import StellantisBaseActionableEntity
from .helpers import preconditioning_program_setter_body


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    for vehicle in data.coordinator.data:
        if jsonpath(
            vehicle.status,
            "$.preconditioning.airConditioning",
        ):
            async_add_entities(
                [
                    StellantisPreconditioningProgramStartTime(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                        slot,
                    )
                    for slot in range(1, 5)
                ]
            )

        if jsonpath(
            vehicle.status,
            "$.energies[?(@.type == 'Electric')]",
        ):
            async_add_entities(
                (
                    StellantisChargingTime(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                    ),
                )
            )


class StellantisPreconditioningProgramStartTime(
    StellantisBaseActionableEntity[time], TimeEntity
):
    """Representation of a Stellantis preconditioning start time of a program."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
        slot: int,
    ) -> None:
        """Initialize the Stellantis preconditioning start time."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            TimeEntityDescription(
                key=f"preconditioning_program_{slot}_start_time",
                translation_key=f"preconditioning_program_{slot}_start_time",
            ),
            entry,
        )
        self.slot = slot
        self._attr_native_value = None

    @property
    def status_value(self):
        """Return the state reported from the API."""
        return self.get_from_vehicle_status(
            f"$.preconditioning.airConditioning.programs[?(@.slot == {self.slot})]"
        )

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        if self._attr_native_value is not None:
            ret = self._attr_native_value
            self._attr_native_value = None
            return ret

        program = self.status_value
        if (
            not program
            or ATTR_START not in program
            or (start_time := dt_util.parse_duration(program[ATTR_START])) is None
        ):
            return None

        return (datetime(1, 1, 1) + start_time).time()

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        try:
            _ = self.status_value
        except KeyError:
            return False
        return super().available

    async def async_set_value(self, value: time) -> None:
        """Set the start of the preconditioning program."""
        program = self.get_from_vehicle_status(
            f"$.preconditioning.airConditioning.programs[?(@.slot == {self.slot})]"
        )

        if not program:
            raise HomeAssistantError(
                f"Preconditioning program {self.slot} does not exists, define it first using stellantis.set_preconditioning_program service"
            )

        program[ATTR_START] = f"PT{value.hour}H{value.minute}M"
        await self.async_call_remote_action(
            preconditioning_program_setter_body(program),
            value,
            f"set preconditioning program {self.slot} start time",
        )


class StellantisChargingTime(StellantisBaseActionableEntity[time], TimeEntity):
    """Representation of a Stellantis charging time."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Stellantis charging time."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            TimeEntityDescription(
                key="charging_time",
                translation_key="charging_time",
            ),
            entry,
        )
        self._attr_native_value = None

    @property
    def status_value(self):
        """Return the state reported from the API."""
        return self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.nextDelayedTime"
        )

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        if self._attr_native_value is not None:
            ret = self._attr_native_value
            self._attr_native_value = None
            return ret

        raw_value = self.status_value
        if not raw_value or (value := dt_util.parse_duration(raw_value)) is None:
            return None

        return (datetime(1, 1, 1) + value).time()

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        try:
            _ = self.status_value
        except KeyError:
            return False
        return super().available

    async def async_set_value(self, value: time) -> None:
        """Set the start of the charging program."""
        await self.async_call_remote_action(
            {
                "charging": {
                    "schedule": {"nextDelayedTime": f"PT{value.hour}H{value.minute}M"}
                }
            },
            value,
            "set next charging time",
        )
