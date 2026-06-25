# AOK Curtain Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub License](https://img.shields.io/github/license/magicbear/hass-aoksz)

Home Assistant custom integration for **AOK (奥科伟业)** electric curtain motors over TCP.

## Features

- Config flow with connection validation
- Reconfigure flow for host, port, scan interval, and device mapping
- Cover control: open, close, stop, and set position
- Multi-curtain support via `device_id` bitmask configuration
- Brand icons for device registry

## Requirements

- Home Assistant 2023.9.0+

## Install (HACS custom repository)

1. Open **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/magicbear/hass-aoksz`
3. Category: **Integration**
4. Install **AOK**, restart Home Assistant
5. Add via **Settings → Devices & services → Add integration → AOK**

### Device ID format

```
1,65535;2,65535;3,65535
```

Format: `GROUP_ID,CHANNEL_BITMASK` pairs separated by `;`. Each bit in the mask represents one curtain channel on that group.

## Links

- [Documentation](https://github.com/magicbear/hass-aoksz)
- [Issue tracker](https://github.com/magicbear/hass-aoksz/issues)

---

## 中文说明

让 Home Assistant 支持 AOK-奥科伟业 电动窗帘设备。

### 安装（HACS 自定义仓库）

1. 进入 **HACS → 集成 → 右上角 ⋮ → 自定义仓库**
2. 仓库地址：`https://github.com/magicbear/hass-aoksz`
3. 类别：**集成**
4. 安装 **AOK** 并重启 Home Assistant
5. 在 **设置 → 设备与服务** 中添加集成，搜索 `AOK`

### 设备 ID 格式

```
1,65535;2,65535;3,65535
```

格式为 `组号,通道位掩码`，多组用 `;` 分隔。掩码每一位代表该组上的一个窗帘通道。