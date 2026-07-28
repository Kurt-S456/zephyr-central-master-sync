# SPI Timestamp Exchange

This project contains a single Zephyr application with two build variants:

- controller (referred to as worker in the accompanying paper): sends its uptime timestamp over SPI
- target (referred to as child in the accompanying paper): receives and decodes the worker timestamp, then captures and prints its local receive-side uptime

Both sides use `spi_transceive()` only, with 8-bit words and MSB-first transfer order.

SPI is electrically full-duplex, so both directions clock bytes every transfer. This project uses a unidirectional application protocol: worker -> child payload only. The reverse direction carries dummy bytes for clocking and is ignored at the application level.

## Project Layout

`platformio`
- `src/controller.c` contains the controller (worker) transfer loop
- `src/target.c` contains the target (child) transfer loop
- `src/benchmark_shared.h` contains shared timestamp helpers
- `zephyr/controller.conf` enables the controller role
- `zephyr/target.conf` enables the target role and SPI slave support
- `zephyr/boards/app_controller.overlay` configures SPI1 as master
- `zephyr/boards/app_target.overlay` configures SPI1 as slave

## Wiring

The project is built around SPI1 on the BluePill STM32F103C8 board.

Use these signals between the two boards:

- PA5: SCK
- PA6: MISO
- PA7: MOSI
- PA4: NSS / CS
- GND: common ground

Controller wiring uses the master pinctrl set. Target wiring uses the slave pinctrl set.

## Build Setup

PlatformIO is configured with two environments in `platformio.ini`:

- `bluepill_f103c8_controller`
- `bluepill_f103c8_target`

The controller environment is the default build.

Use `platformio` from your shell path.

## Build Commands

Build the default controller (worker) image:

```sh
platformio run
```

Build the target (child) image:

```sh
platformio run -e bluepill_f103c8_target
```

## Flash Commands

Flash the controller build:

```sh
platformio run -t upload
```

Flash the target build:

```sh
platformio run -e bluepill_f103c8_target -t upload
```

## Serial Monitor

Open the serial monitor for the default controller environment:

```sh
platformio device monitor
```

Open the serial monitor for the target environment:

```sh
platformio device monitor -e bluepill_f103c8_target
```

## Data Format

The controller serializes `k_uptime_get()` into 8 bytes using this layout:

```c
TX_i = (T_worker >> (56 - 8 * i)) & 0xFF
```

The target decodes the received buffer with the matching shift-and-OR loop, then prints the received worker timestamp and its own local capture timestamp.

## Notes

- The app prints timestamps to the serial console on both sides.
- SPI is configured for 8-bit words and MSB-first transfers.
- The implementation intentionally keeps application data flow one-way (worker -> child) while still using `spi_transceive()` on both nodes.
- The worker resynchronization interval is 15 seconds.
- Each experiment runs for 240 sync cycles, so nominal duration is 3600 seconds (1 hour).
- The application keeps the role selection in the build configuration rather than in runtime arguments.