## AOK Curtain for Home Assistant — v1.1.0

TCP integration for AOK (奥科伟业) electric curtain motors.

### Highlights

- Config flow with connection validation and reconfigure support
- Multi-device mapping via group/channel bitmask configuration
- Cover entities with open, close, stop, and position control
- Brand icons and consolidated timeout logging
- Hassfest & HACS Action validated

### Requirements

- Home Assistant 2023.9.0+

### Install (HACS)

1. Add custom repo: `https://github.com/magicbear/hass-aoksz` (Integration)
2. Install **AOK** and restart HA
3. Add integration via **Settings → Devices & services**