import asyncio
import time
from asyncio import ensure_future
from collections import defaultdict
from importlib import reload

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_DEVICE_ID, CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
import logging
from datetime import timedelta
from functools import partial, wraps
from functools import reduce
from operator import xor
import struct
import math

_LOGGER = logging.getLogger(__name__)


class AOKProtocol(asyncio.Protocol):
    _stopped: bool = False
    _connected: bool = False
    _connecting: bool = False

    def __init__(self, host, port, loop=None):
        self._cmdServer = host
        self._cmdServerPort = port
        self._transport = None
        self._updateCallbacks = []
        self.initialised = asyncio.Event()
        self.state_received = asyncio.Event()
        self.name = ""
        self.buffer = bytearray()
        self.devices = {}

        if loop:
            _LOGGER.debug("Latching onto an existing event loop")
            self._eventLoop = loop

    def connection_made(self, transport):
        """asyncio callback for a successful connection."""
        _LOGGER.debug("Connected to Black Magic Smart Video Hub API")
        self._transport = transport
        self._connected = True
        self._connecting = False

    def data_received(self, data):
        """asyncio callback when data is received on the socket"""
        self.buffer += data
        while len(self.buffer) > 0 and self.buffer[0] != 0xd8:
            _LOGGER.debug("Invalid buffer, cleanup %02x", self.buffer[0])
            self.buffer = self.buffer[1:]
        while len(self.buffer) >= 10:
            rx_buf = self.buffer[0:10]
            self.buffer = self.buffer[10:]
            chk_sum = self.compute_fcs(rx_buf[1:9])
            if chk_sum != rx_buf[9]:
                _LOGGER.warning(f"checksum error {chk_sum} != {rx_buf[9]}")
            else:
                group, channels, currents, voltage, rpms, position, flags, = struct.unpack("<BHBBBBB", rx_buf[1:9])
                if channels != 0:
                    channel_id = int(math.log(channels, 2)) + 1
                    self.devices[(group, channel_id)] = {
                        "last_update": time.time(),
                        "group": group,
                        "channel_id": channel_id,
                        "currents": currents,
                        "voltage": voltage,
                        "position": position,
                        "rpms": rpms,
                        "flags": flags,
                    }
                    self.state_received.set()

    def connection_lost(self, exc):
        """asyncio callback for a lost TCP connection"""
        self._connected = False
        self.initialised.set()
        self.state_received.set()
        self._send_update_callback()
        _LOGGER.error("Connection to the server lost")
        if not self._stopped:
            self.connect()

    def connect(self):
        if self._connected:
            return ensure_future(asyncio.sleep(0))

        _LOGGER.info(
            str.format(
                "Connecting to Hub at {0}:{1}",
                self._cmdServer,
                self._cmdServerPort,
            )
        )
        self._stopped = False
        self._connecting = True
        coro = self._eventLoop.create_connection(
            lambda: self, self._cmdServer, self._cmdServerPort
        )
        return ensure_future(coro)

    def close(self):
        """Public method for shutting down connectivity with the envisalink."""
        self._connected = False
        self._stopped = True
        self._transport.close()

    @staticmethod
    def compute_fcs(msg):
        return reduce(xor, msg)

    @staticmethod
    def getControlPackage(id, channel, cmd_type, cmd):
        buf = struct.pack("<BBHBB", 0x9a, id, channel, cmd_type, cmd)
        buf += struct.pack("!B", reduce(xor, buf[1:]))
        return buf

    async def get_state(self, group, channel, timeout=1):
        if not self._connected:
            raise ConnectionResetError

        self.state_received.clear()
        self._transport.write(self.getControlPackage(group, channel, 0xcc, 0x00))
        await asyncio.wait_for(self.state_received.wait(), timeout=timeout)

        dev_data = self.devices[(group, int(math.log(channel, 2)) + 1)]
        if time.time() - dev_data['last_update'] < 1:
            return dev_data
        else:
            raise KeyError

    def open_cover(self, group, channel):
        if not self._connected:
            raise ConnectionResetError
        self._transport.write(self.getControlPackage(group, channel, 0x0a, 0xee))

    def close_cover(self, group, channel):
        if not self._connected:
            raise ConnectionResetError
        self._transport.write(self.getControlPackage(group, channel, 0x0a, 0xdd))

    def stop_cover(self, group, channel):
        if not self._connected:
            raise ConnectionResetError
        self._transport.write(self.getControlPackage(group, channel, 0x0a, 0xcc))

    def set_cover_position(self, group, channel, position):
        if not self._connected:
            raise ConnectionResetError
        self._transport.write(self.getControlPackage(group, channel, 0xdd, position))

    def _send_update_callback(self):
        """Internal method to notify all update callback subscribers."""

        for callback in self._updateCallbacks:
            callback()

    @property
    def connected(self):
        return self._connected

class AOKDataCoordinator(DataUpdateCoordinator):
    """异步数据协调器"""

    def __init__(self, hass, config_entry, client):
        host, port = config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
        super().__init__(
            hass,
            logger=_LOGGER,
            name="AOK Cover",
            update_interval=timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]),
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="AOK",
            manufacturer="奥科伟业",
            model=None
        )
        self.client = client
        self.device_lists = []
        for group in config_entry.data[CONF_DEVICE_ID].split(";"):
            _id, mask = map(lambda x: int(x), group.split(","))

            # 遍历所有设置的位（无需循环16次）
            bit = 0
            while mask:
                # 提取最低有效位的值（如 mask=0b1010 → lsb=0b10）
                lsb = mask & -mask
                self.device_lists.append([_id, lsb])
                # 清除已处理的最低位
                mask ^= lsb
                bit += 1

        self.data = defaultdict(dict)

    async def _async_update_data(self):
        """异步获取所有数据"""
        try:
            # 连接检查
            if not self.client.connected:
                await self.client.connect()

            if not self.client.connected:
                raise Exception("Connection lost")

            groups = {group: 0 for group, q_channel_id in self.device_lists}
            timeout_devices: list[str] = []

            for group, q_channel_id in self.device_lists:
                channel_id = int(math.log(q_channel_id, 2)) + 1
                key = "%02d-%02d" % (group, channel_id)
                try:
                    self.data[key] = await self.client.get_state(group, q_channel_id, 0.2)
                    groups[group] |= self.data[key]['flags']
                    self.data['%02d-00' % group].update(self.data[key])
                except asyncio.exceptions.TimeoutError:
                    self.data[key] = None
                    timeout_devices.append(key)

            if timeout_devices:
                _LOGGER.warning(
                    "Query device timeout (%d/%d): %s",
                    len(timeout_devices),
                    len(self.device_lists),
                    ", ".join(timeout_devices),
                )

            for group in groups:
                self.data['%02d-00' % group]['flags'] = groups[group]
            return self.data
        except Exception as e:
            self.logger.error("Update failed: %s", str(e))
            self.client.close()
            raise


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    from . import cover
    reload(cover)
    hass.data.setdefault(DOMAIN, {})

    client = AOKProtocol(config_entry.data[CONF_HOST], config_entry.data[CONF_PORT], hass.loop)
    coord = AOKDataCoordinator(hass, config_entry, client)
    hass.data[DOMAIN][config_entry.entry_id] = {
        'client': client,
        'coord': coord
    }

    # 尝试建立初始连接并验证配置
    try:
        if not client.connected:
            await client.connect()

        # 等待第一次数据更新以确认设备可用
        await coord.async_config_entry_first_refresh()
    except Exception as ex:
        # 在调用 async_forward_entry_setups 之前抛出 ConfigEntryNotReady
        raise ConfigEntryNotReady(f"Failed to initialize AOK device: {ex}") from ex

    await hass.config_entries.async_forward_entry_setups(config_entry, [Platform.COVER])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.COVER]
    )
    return unload_ok
