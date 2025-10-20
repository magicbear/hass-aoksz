# cover.py
import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.cover import CoverEntity, CoverEntityDescription, CoverDeviceClass, CoverEntityFeature, ENTITY_ID_FORMAT
from homeassistant.helpers.entity import async_generate_entity_id, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.const import ConfigEntryState
from .const import *
import math

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]['coord']
    client = hass.data[DOMAIN][config_entry.entry_id]['client']

    # 只有在首次设置时才需要强制刷新
    if config_entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        await coordinator.async_config_entry_first_refresh()
    else:
        # 确保协调器已初始化（可选）
        if not coordinator.last_update_success:
            await coordinator.async_request_refresh()

    # 确保update_interval类型正确
    if not isinstance(coordinator.update_interval, timedelta):
        raise ValueError("Invalid update interval type")

    groups = {grp_id for grp_id, dev in coordinator.device_lists}
    covers = [
        AOKCover(coordinator, dev, hass, client)
        for dev in coordinator.device_lists
    ]
    covers.extend([
       AOKCover(coordinator, (dev, 0xffff), hass, client)
       for dev in groups
    ])
    async_add_entities(
        covers
    )


class AOKCover(CoordinatorEntity, CoverEntity):
    _attr_supported_features = (CoverEntityFeature.OPEN |
                                CoverEntityFeature.CLOSE |
                                CoverEntityFeature.SET_POSITION |
                                CoverEntityFeature.STOP
                                )
    def __init__(self, coordinator, dev, hass, client):
        channel_id = int(math.log(dev[1], 2)) + 1
        if dev[1] == 0xffff:
            channel_id = 0
        key = "%02d-%02d" % (dev[0], channel_id)
        super().__init__(coordinator, key)

        self.client = client
        self._data_key = dev
        self._attr_unique_id = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name="AOK %s" % key,
            manufacturer="奥科伟业",
            model=None
        )
        if channel_id != 0:
            self._attr_device_info['via_device'] = (DOMAIN, "%02d-%02d" % (dev[0], 0))
        self._attr_translation_key = key
        self.entity_description = CoverEntityDescription(
            key=key,
            name="AOK Cover %s" % key,
            device_class=CoverDeviceClass.SHUTTER
        )
        self.update()

    def update(self):
        data = self.coordinator.data.get(self.entity_description.key, None)
        if data is None or not self.client.connected:
            self._attr_available = False
            self._attr_is_closed = True

        else:
            self._attr_available = True
            self._attr_is_closing = data['flags'] & 0x1
            self._attr_is_opening = data['flags'] & 0x1
            self._attr_is_closed = data['position'] == 0
            self._attr_current_cover_position = data['position']

    async def async_open_cover(self):
        self._attr_is_opening = True
        self._attr_is_closing = False
        self._attr_is_closed = False
        self.client.open_cover(self._data_key[0], self._data_key[1])
        self.async_write_ha_state()

    async def async_close_cover(self):
        self._attr_is_closing = True
        self._attr_is_opening = False
        self._attr_is_closed = False
        self.client.close_cover(self._data_key[0], self._data_key[1])
        self.async_write_ha_state()

    async def async_stop_cover(self):
        self._attr_is_opening = False
        self._attr_is_closing = False
        self.client.stop_cover(self._data_key[0], self._data_key[1])
        self.async_write_ha_state()

    async def async_set_cover_position(self, position):
        self._attr_current_cover_position = position
        self._attr_is_closed = False
        self.client.set_cover_position(self._data_key[0], self._data_key[1], position)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """处理来自协调器的更新数据。"""
        self.update()
        self.async_write_ha_state()
