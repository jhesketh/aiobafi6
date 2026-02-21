# Tools

## fan_tui.py

A [Textual](https://textual.textualize.io/)-based TUI for interactive control
of Big Ass Fans over the i6 protocol. Connects to a fan by hostname or IP and
provides real-time, bidirectional control — changes made via the TUI, the BAF
Android/iOS app, or the physical remote are all reflected instantly.

### Requirements

```
pip install textual
```

### Usage

```
python tools/fan_tui.py <hostname-or-ip>
python tools/fan_tui.py 192.168.1.100
python tools/fan_tui.py MyFan.local
```

### Tabs

| Tab | Controls |
|---|---|
| **Fan** | Mode (OFF/ON/AUTO), speed, whoosh, eco, reverse. Comfort settings (auto comfort, ideal temperature, min/max speed, heat assist). Motion sense and return-to-auto with timeouts. Unoccupied behavior (Smart Mix toggle and speed). |
| **Light** | Mode (OFF/ON/AUTO), brightness, color temperature, dim-to-warm. Motion timeout and return-to-auto with timeouts. |
| **Nightlight** | Enable/disable, brightness, color presets and raw value slider |
| **Sensors** | Temperature, humidity, RPM (current/target), fan/light occupancy (read-only) |
| **Settings** | LED indicators, fan beep, IR remote |

### Notes

- The fan pushes most state changes over the persistent TCP connection, so
  updates from other clients appear immediately without polling.
- Adjusting fan speed or light brightness while in AUTO mode automatically
  switches the mode to ON, matching the behaviour of the official app.
- Nightlight color supports 9 values: Red (1), Green (2), Blue (3),
  Teal (4), Yellow (5), Purple (6), White (7), Orange (8), Pink (9).
  The BAF Android app exposes 7 of these, omitting Blue and White.
- Smart Mix speed changes are accepted by the fan. The BAF Android app may
  not reflect them until it is restarted; this appears to be a limitation
  of the app rather than the firmware.
- Light and Nightlight tabs are hidden if the connected fan does not report
  the corresponding capabilities.
