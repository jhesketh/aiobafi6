#!/usr/bin/env python3
"""TUI control app for Big Ass Fans using the aiobafi6 library."""
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    Rule,
    Static,
    Switch,
    TabPane,
    TabbedContent,
)

from aiobafi6 import PORT, Device, OffOnAuto, Service

NIGHTLIGHT_COLORS = [
    (1, "Red"),
    (8, "Orange"),
    (5, "Yellow"),
    (2, "Green"),
    (4, "Teal"),
    (6, "Purple"),
    (9, "Pink"),
    (3, "?3"),
    (7, "?7"),
    (10, "?10"),
]


# ---------------------------------------------------------------------------
# Custom compound widget: labeled value bar with +/- controls
# ---------------------------------------------------------------------------
class ValueBar(Static):
    """A labeled value control with [-] / [+] buttons and a progress bar."""

    value: reactive[int] = reactive(0, init=False)

    class Changed(Message):
        def __init__(self, widget: ValueBar, value: int) -> None:
            super().__init__()
            self.widget = widget
            self.value = value

    def __init__(
        self,
        label: str,
        min_val: int = 0,
        max_val: int = 100,
        step: int = 1,
        unit: str = "",
        bar_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._label_text = label
        self._min = min_val
        self._max = max_val
        self._step = step
        self._unit = unit
        self._bar_id = bar_id or self.id or "bar"
        self._suppress = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="value-bar"):
            yield Label(self._label_text, classes="vb-label")
            yield Button("-", id=f"{self._bar_id}-dec", classes="vb-btn")
            yield ProgressBar(
                total=self._max - self._min,
                show_eta=False,
                show_percentage=False,
                id=f"{self._bar_id}-progress",
                classes="vb-progress",
            )
            yield Button("+", id=f"{self._bar_id}-inc", classes="vb-btn")
            yield Label(
                self._format(self.value),
                id=f"{self._bar_id}-val",
                classes="vb-val",
            )

    def _format(self, v: int) -> str:
        return f"{v}{self._unit}"

    def watch_value(self, new_value: int) -> None:
        try:
            bar = self.query_one(f"#{self._bar_id}-progress", ProgressBar)
            bar.update(progress=float(new_value - self._min))
            lbl = self.query_one(f"#{self._bar_id}-val", Label)
            lbl.update(self._format(new_value))
        except Exception:
            pass

    def set_value_quiet(self, v: int) -> None:
        """Set value without emitting Changed."""
        self._suppress = True
        self.value = max(self._min, min(self._max, v))
        self._suppress = False

    @on(Button.Pressed)
    def _on_button(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == f"{self._bar_id}-dec":
            new = max(self._min, self.value - self._step)
        elif event.button.id == f"{self._bar_id}-inc":
            new = min(self._max, self.value + self._step)
        else:
            return
        if new != self.value:
            self.value = new
            if not self._suppress:
                self.post_message(self.Changed(self, self.value))


# ---------------------------------------------------------------------------
# Mode selector (OFF / ON / AUTO)
# ---------------------------------------------------------------------------
class ModeSelector(Static):
    """RadioSet-based OFF/ON/AUTO selector."""

    class Changed(Message):
        def __init__(self, widget: ModeSelector, value: OffOnAuto) -> None:
            super().__init__()
            self.widget = widget
            self.value = value

    def __init__(self, label: str, sel_id: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._label_text = label
        self._sel_id = sel_id or self.id or "mode"
        self._suppress = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="mode-selector"):
            yield Label(self._label_text, classes="vb-label")
            yield RadioSet(
                RadioButton("OFF", id=f"{self._sel_id}-off"),
                RadioButton("ON", id=f"{self._sel_id}-on"),
                RadioButton("AUTO", id=f"{self._sel_id}-auto"),
                id=f"{self._sel_id}-rset",
                classes="ms-radioset",
            )

    def set_value_quiet(self, mode: OffOnAuto) -> None:
        self._suppress = True
        try:
            suffixes = {OffOnAuto.OFF: "off", OffOnAuto.ON: "on", OffOnAuto.AUTO: "auto"}
            btn = self.query_one(f"#{self._sel_id}-{suffixes[mode]}", RadioButton)
            btn.value = True
        except Exception:
            pass
        self._suppress = False

    @on(RadioSet.Changed)
    def _on_radio_changed(self, event: RadioSet.Changed) -> None:
        event.stop()
        if not self._suppress:
            self.post_message(self.Changed(self, OffOnAuto(event.radio_set.pressed_index)))


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
class FanApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    .value-bar {
        height: 3;
        align: left middle;
    }
    .vb-label {
        width: 20;
        padding: 1 1;
    }
    .vb-btn {
        width: 5;
        min-width: 5;
    }
    .vb-progress {
        width: 1fr;
        padding: 0 1;
    }
    .vb-val {
        width: 12;
        padding: 1 1;
        text-align: right;
    }
    .mode-selector {
        height: 3;
        align: left middle;
    }
    .ms-radioset {
        layout: horizontal;
        height: 3;
    }
    .toggle-row {
        height: 3;
        align: left middle;
        padding: 0 1;
    }
    .toggle-row Label {
        padding: 1 1;
        width: 20;
    }
    .toggle-row Switch {
        width: auto;
    }
    .info-row {
        height: 3;
        padding: 0 2;
    }
    .info-row Label {
        padding: 1 1;
    }
    .section-title {
        padding: 1 2;
        text-style: bold;
        color: $accent;
    }
    .nl-presets {
        height: auto;
        padding: 0 1;
    }
    .nl-preset-btn {
        min-width: 10;
        margin: 0 1;
    }
    .nl-preset-btn.-active {
        background: $accent;
        color: $text;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 2;
        background: $surface;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    TITLE = "Big Ass Fan Control"

    def __init__(self, host: str, port: int = PORT) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._device: Optional[Device] = None
        self._updating = False

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Fan", id="tab-fan"):
                yield ModeSelector("Mode", sel_id="fan-mode", id="fan-mode-sel")
                yield ValueBar("Speed", min_val=0, max_val=7, step=1, id="fan-speed")
                yield Rule()
                with Horizontal(classes="toggle-row"):
                    yield Label("Whoosh")
                    yield Switch(id="whoosh-sw")
                with Horizontal(classes="toggle-row"):
                    yield Label("Eco")
                    yield Switch(id="eco-sw")
                with Horizontal(classes="toggle-row"):
                    yield Label("Reverse")
                    yield Switch(id="reverse-sw")
                yield Rule()
                with Horizontal(classes="info-row"):
                    yield Label("RPM:", classes="vb-label")
                    yield Label("--", id="rpm-label")

            with TabPane("Light", id="tab-light"):
                yield ModeSelector("Mode", sel_id="light-mode", id="light-mode-sel")
                yield ValueBar(
                    "Brightness",
                    min_val=0,
                    max_val=100,
                    step=5,
                    unit="%",
                    bar_id="light-bright",
                    id="light-bright-bar",
                )
                yield ValueBar(
                    "Color Temp",
                    min_val=2200,
                    max_val=5000,
                    step=100,
                    unit="K",
                    bar_id="light-ct",
                    id="light-ct-bar",
                )
                yield Rule()
                with Horizontal(classes="toggle-row"):
                    yield Label("Dim to Warm")
                    yield Switch(id="dtw-sw")

            with TabPane("Nightlight", id="tab-nightlight"):
                with Horizontal(classes="toggle-row"):
                    yield Label("Enabled")
                    yield Switch(id="nl-enabled-sw")
                yield ValueBar(
                    "Brightness",
                    min_val=1,
                    max_val=100,
                    step=5,
                    unit="%",
                    bar_id="nl-bright",
                    id="nl-bright-bar",
                )
                yield ValueBar(
                    "Color (raw)",
                    min_val=1,
                    max_val=10,
                    step=1,
                    bar_id="nl-color",
                    id="nl-color-bar",
                )
                yield Label("Presets:", classes="section-title")
                with Horizontal(classes="nl-presets", id="nl-presets"):
                    for val, name in NIGHTLIGHT_COLORS:
                        yield Button(
                            name, id=f"nl-c-{val}", classes="nl-preset-btn"
                        )

            with TabPane("Sensors", id="tab-sensors"):
                with Horizontal(classes="info-row"):
                    yield Label("Temperature:", classes="vb-label")
                    yield Label("--", id="temp-label")
                with Horizontal(classes="info-row"):
                    yield Label("Humidity:", classes="vb-label")
                    yield Label("--", id="humidity-label")
                with Horizontal(classes="info-row"):
                    yield Label("Occupancy (fan):", classes="vb-label")
                    yield Label("--", id="fan-occ-label")
                with Horizontal(classes="info-row"):
                    yield Label("Occupancy (light):", classes="vb-label")
                    yield Label("--", id="light-occ-label")

            with TabPane("Settings", id="tab-settings"):
                with Horizontal(classes="toggle-row"):
                    yield Label("LED Indicators")
                    yield Switch(id="led-sw")
                with Horizontal(classes="toggle-row"):
                    yield Label("Fan Beep")
                    yield Switch(id="beep-sw")
                with Horizontal(classes="toggle-row"):
                    yield Label("IR Remote")
                    yield Switch(id="ir-sw")

        yield Label("Connecting...", id="status-bar")
        yield Footer()

    # -- lifecycle -----------------------------------------------------------

    async def on_mount(self) -> None:
        self._connect_device()

    @work(exclusive=True)
    async def _connect_device(self) -> None:
        status = self.query_one("#status-bar", Label)
        status.update(f"Resolving {self._host}...")

        try:
            infos = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: socket.getaddrinfo(
                    self._host, self._port, socket.AF_INET, socket.SOCK_STREAM
                ),
            )
            ip = infos[0][4][0]
        except Exception as exc:
            status.update(f"DNS resolution failed: {exc}")
            return

        status.update(f"Connecting to {ip}:{self._port}...")

        dev = Device(
            Service(ip_addresses=[ip], port=self._port),
            query_interval_seconds=60,
            ignore_volatile_props=False,
        )
        self._device = dev
        dev.add_callback(self._on_device_update)
        dev.async_run()

        try:
            await asyncio.wait_for(dev.async_wait_available(), timeout=10)
        except asyncio.TimeoutError:
            status.update(f"Connection to {ip} timed out – retrying in background...")
            return

        self._refresh_all()

    def _on_device_update(self, dev: Device) -> None:
        # The callback fires on the same asyncio loop that Textual uses,
        # so we can refresh directly. Using call_from_thread would add
        # unnecessary latency by bouncing through thread-safe scheduling.
        self._refresh_all()

    # -- refresh UI from device state ----------------------------------------

    def _refresh_all(self) -> None:
        dev = self._device
        if dev is None:
            return
        self._updating = True
        try:
            self._refresh_header(dev)
            self._refresh_fan(dev)
            self._refresh_light(dev)
            self._refresh_nightlight(dev)
            self._refresh_sensors(dev)
            self._refresh_settings(dev)
        finally:
            self._updating = False

    def _refresh_header(self, dev: Device) -> None:
        name = dev.name or "Unknown"
        model = dev.model or ""
        fw = dev.firmware_version or ""
        ip = dev.ip_address or ""
        avail = "Connected" if dev.available else "Connecting..."
        self.title = f"{name}"
        self.sub_title = f"{model}  FW {fw}  {ip}  [{avail}]"
        status = self.query_one("#status-bar", Label)
        status.update(f"{name} | {model} | {ip} | {avail}")

    def _refresh_fan(self, dev: Device) -> None:
        mode = dev.fan_mode
        if mode is not None:
            self.query_one("#fan-mode-sel", ModeSelector).set_value_quiet(OffOnAuto(mode))

        speed = dev.speed
        if speed is not None:
            self.query_one("#fan-speed", ValueBar).set_value_quiet(speed)

        whoosh = dev.whoosh_enable
        if whoosh is not None:
            self.query_one("#whoosh-sw", Switch).value = whoosh
        eco = dev.eco_enable
        if eco is not None:
            self.query_one("#eco-sw", Switch).value = eco
        rev = dev.reverse_enable
        if rev is not None:
            self.query_one("#reverse-sw", Switch).value = rev

        rpm = dev.current_rpm
        target = dev.target_rpm
        rpm_text = f"{rpm}" if rpm is not None else "--"
        if target is not None:
            rpm_text += f" / target {target}"
        self.query_one("#rpm-label", Label).update(rpm_text)

    def _refresh_light(self, dev: Device) -> None:
        if not dev.has_any_light:
            try:
                self.query_one("#tab-light", TabPane).display = False
            except Exception:
                pass
            return

        mode = dev.light_mode
        if mode is not None:
            self.query_one("#light-mode-sel", ModeSelector).set_value_quiet(OffOnAuto(mode))

        bright = dev.light_brightness_percent
        if bright is not None:
            self.query_one("#light-bright-bar", ValueBar).set_value_quiet(bright)

        ct = dev.light_color_temperature
        warmest = dev.light_warmest_color_temperature
        coolest = dev.light_coolest_color_temperature
        ct_bar = self.query_one("#light-ct-bar", ValueBar)
        if warmest is not None and coolest is not None:
            ct_bar._min = warmest
            ct_bar._max = coolest
            try:
                bar = ct_bar.query_one(f"#light-ct-progress", ProgressBar)
                bar.total = float(coolest - warmest)
            except Exception:
                pass
        if ct is not None:
            ct_bar.set_value_quiet(ct)

        dtw = dev.light_dim_to_warm_enable
        if dtw is not None:
            self.query_one("#dtw-sw", Switch).value = dtw

    def _refresh_nightlight(self, dev: Device) -> None:
        if not dev.has_nightlight:
            try:
                self.query_one("#tab-nightlight", TabPane).display = False
            except Exception:
                pass
            return

        enabled = dev.nightlight_enabled
        if enabled is not None:
            self.query_one("#nl-enabled-sw", Switch).value = enabled

        bright = dev.nightlight_brightness_percent
        if bright is not None:
            self.query_one("#nl-bright-bar", ValueBar).set_value_quiet(bright)

        color = dev.nightlight_color
        if color is not None:
            self.query_one("#nl-color-bar", ValueBar).set_value_quiet(color)
            for btn in self.query(".nl-preset-btn"):
                btn.remove_class("-active")
            try:
                self.query_one(f"#nl-c-{color}", Button).add_class("-active")
            except Exception:
                pass

    def _refresh_sensors(self, dev: Device) -> None:
        temp = dev.temperature
        if temp is not None:
            self.query_one("#temp-label", Label).update(f"{temp:.1f} °C")
        hum = dev.humidity
        if hum is not None:
            self.query_one("#humidity-label", Label).update(f"{hum}%")
        fan_occ = dev.fan_occupancy_detected
        if fan_occ is not None:
            self.query_one("#fan-occ-label", Label).update("Yes" if fan_occ else "No")
        light_occ = dev.light_occupancy_detected
        if light_occ is not None:
            self.query_one("#light-occ-label", Label).update("Yes" if light_occ else "No")

    def _refresh_settings(self, dev: Device) -> None:
        led = dev.led_indicators_enable
        if led is not None:
            self.query_one("#led-sw", Switch).value = led
        beep = dev.fan_beep_enable
        if beep is not None:
            self.query_one("#beep-sw", Switch).value = beep
        ir = dev.legacy_ir_remote_enable
        if ir is not None:
            self.query_one("#ir-sw", Switch).value = ir

    # -- handle user input ---------------------------------------------------

    @on(ModeSelector.Changed)
    def _on_mode_changed(self, event: ModeSelector.Changed) -> None:
        if self._updating or self._device is None:
            return
        wid = event.widget.id
        if wid == "fan-mode-sel":
            self._device.fan_mode = event.value
        elif wid == "light-mode-sel":
            self._device.light_mode = event.value

    @on(ValueBar.Changed)
    def _on_value_changed(self, event: ValueBar.Changed) -> None:
        if self._updating or self._device is None:
            return
        dev = self._device
        wid = event.widget.id
        if wid == "fan-speed":
            if dev.fan_mode is not None and OffOnAuto(dev.fan_mode) != OffOnAuto.ON:
                dev.fan_mode = OffOnAuto.ON
            dev.speed = event.value
        elif wid == "light-bright-bar":
            if dev.light_mode is not None and OffOnAuto(dev.light_mode) != OffOnAuto.ON:
                dev.light_mode = OffOnAuto.ON
            dev.light_brightness_percent = event.value
        elif wid == "light-ct-bar":
            if dev.light_mode is not None and OffOnAuto(dev.light_mode) != OffOnAuto.ON:
                dev.light_mode = OffOnAuto.ON
            dev.light_color_temperature = event.value
        elif wid == "nl-bright-bar":
            dev.nightlight_brightness_percent = event.value
        elif wid == "nl-color-bar":
            dev.nightlight_color = event.value

    @on(Button.Pressed, ".nl-preset-btn")
    def _on_nl_color_preset(self, event: Button.Pressed) -> None:
        if self._updating or self._device is None:
            return
        bid = event.button.id or ""
        if bid.startswith("nl-c-"):
            val = int(bid.removeprefix("nl-c-"))
            self._device.nightlight_color = val

    @on(Switch.Changed)
    def _on_switch_changed(self, event: Switch.Changed) -> None:
        if self._updating or self._device is None:
            return
        sid = event.switch.id
        val = event.value
        dev = self._device
        switch_map = {
            "whoosh-sw": "whoosh_enable",
            "eco-sw": "eco_enable",
            "reverse-sw": "reverse_enable",
            "dtw-sw": "light_dim_to_warm_enable",
            "nl-enabled-sw": "nightlight_enabled",
            "led-sw": "led_indicators_enable",
            "beep-sw": "fan_beep_enable",
            "ir-sw": "legacy_ir_remote_enable",
        }
        attr = switch_map.get(sid)
        if attr:
            setattr(dev, attr, val)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="TUI control for Big Ass Fans")
    parser.add_argument("host", help="Fan hostname or IP address")
    parser.add_argument(
        "-p", "--port", type=int, default=PORT, help=f"Port (default {PORT})"
    )
    args = parser.parse_args()
    app = FanApp(args.host, args.port)
    app.run()


if __name__ == "__main__":
    main()
