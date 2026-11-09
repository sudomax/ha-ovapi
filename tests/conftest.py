import sys
import types
from unittest.mock import MagicMock

# If homeassistant is not installed in the environment (e.g. running outside full HA container),
# inject lightweight testing stubs that match HA's architecture.
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.core
    core = types.ModuleType("homeassistant.core")

    def callback(func):
        return func

    core.callback = callback

    class HomeAssistant:
        def __init__(self):
            self.data = {}
            self.config_entries = MagicMock()
            self.helpers = MagicMock()

    core.HomeAssistant = HomeAssistant
    ha.core = core
    sys.modules["homeassistant.core"] = core

    # homeassistant.const
    const = types.ModuleType("homeassistant.const")

    class Platform:
        SENSOR = "sensor"

    const.Platform = Platform
    ha.const = const
    sys.modules["homeassistant.const"] = const

    # homeassistant.data_entry_flow
    flow = types.ModuleType("homeassistant.data_entry_flow")
    flow.FlowResult = dict
    ha.data_entry_flow = flow
    sys.modules["homeassistant.data_entry_flow"] = flow

    # homeassistant.config_entries
    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __init__(self, entry_id="test_entry_id", data=None, options=None, title=""):
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self.title = title

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain

        def __init__(self):
            self.hass = HomeAssistant()
            self.unique_id = None
            self.context = {}

        async def async_set_unique_id(self, unique_id):
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            pass

        def async_show_form(self, step_id, data_schema, errors=None, description_placeholders=None):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
                "description_placeholders": description_placeholders or {},
            }

        def async_create_entry(self, title, data):
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
                "result": ConfigEntry(data=data, title=title),
            }

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    ha.config_entries = config_entries
    sys.modules["homeassistant.config_entries"] = config_entries

    # homeassistant.helpers
    helpers = types.ModuleType("homeassistant.helpers")
    ha.helpers = helpers
    sys.modules["homeassistant.helpers"] = helpers

    # homeassistant.helpers.aiohttp_client
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass):
        session = MagicMock()
        session.closed = False
        return session

    aiohttp_client.async_get_clientsession = async_get_clientsession
    helpers.aiohttp_client = aiohttp_client
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

    # homeassistant.helpers.entity
    entity = types.ModuleType("homeassistant.helpers.entity")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            for k, v in kwargs.items():
                setattr(self, k, v)

    entity.DeviceInfo = DeviceInfo
    helpers.entity = entity
    sys.modules["homeassistant.helpers.entity"] = entity

    # homeassistant.helpers.device_registry
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceEntryType:
        SERVICE = "service"

    device_registry.DeviceEntryType = DeviceEntryType
    helpers.device_registry = device_registry
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    # homeassistant.helpers.entity_platform
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = MagicMock()
    helpers.entity_platform = entity_platform
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    # homeassistant.helpers.update_coordinator
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        __class_getitem__ = classmethod(lambda cls, item: cls)

        def __init__(self, hass, logger, name, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None

        async def async_config_entry_first_refresh(self):
            self.data = await self._async_update_data()

        async def _async_update_data(self):
            raise NotImplementedError

    class CoordinatorEntity:
        __class_getitem__ = classmethod(lambda cls, item: cls)

        def __init__(self, coordinator):
            self.coordinator = coordinator

    update_coordinator.UpdateFailed = UpdateFailed
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    helpers.update_coordinator = update_coordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    # homeassistant.components
    components = types.ModuleType("homeassistant.components")
    ha.components = components
    sys.modules["homeassistant.components"] = components

    # homeassistant.components.sensor
    sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:
        TIMESTAMP = "timestamp"

    class SensorEntity:
        _attr_device_class = None
        _attr_has_entity_name = False
        _attr_name = None
        _attr_translation_key = None
        _attr_translation_placeholders = None
        _attr_native_unit_of_measurement = None
        _attr_icon = None
        _attr_unique_id = None
        _attr_device_info = None
        _attr_entity_registry_enabled_default = True

        @property
        def entity_registry_enabled_default(self) -> bool:
            return self._attr_entity_registry_enabled_default

        @property
        def name(self):
            return self._attr_name

        @property
        def translation_key(self):
            return self._attr_translation_key

        @property
        def translation_placeholders(self):
            return self._attr_translation_placeholders or {}

        @property
        def unique_id(self):
            return self._attr_unique_id

        @property
        def icon(self):
            return self._attr_icon

    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorEntity = SensorEntity
    components.sensor = sensor
    sys.modules["homeassistant.components.sensor"] = sensor
