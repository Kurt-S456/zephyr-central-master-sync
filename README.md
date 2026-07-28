# SPI Timestamp Exchange

This project contains a single Zephyr application with two build variants:

- controller: sends its uptime timestamp over SPI and prints the timestamps
- target: receives the timestamp, decodes it, and sends its own uptime back

Both sides use `spi_transceive()` only, with 8-bit words and MSB-first transfer order.

## Project Layout

- `src/main.c` selects the active role at build time
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

If PlatformIO is not on your shell path, use the installed binary directly:

`/home/kurt/.platformio/penv/bin/platformio`

## Build Commands

Build the default controller (worker) image:

```sh
/home/kurt/.platformio/penv/bin/platformio run
```

Build the target (child) image:

```sh
/home/kurt/.platformio/penv/bin/platformio run -e bluepill_f103c8_target
```

If `platformio` is available on your PATH, you can use the shorter form:

```sh
platformio run
platformio run -e bluepill_f103c8_target
```

## Flash Commands

Flash the controller build:

```sh
/home/kurt/.platformio/penv/bin/platformio run -t upload
```

Flash the target build:

```sh
/home/kurt/.platformio/penv/bin/platformio run -e bluepill_f103c8_target -t upload
```

## Serial Monitor

Open the serial monitor for the default controller environment:

```sh
/home/kurt/.platformio/penv/bin/platformio device monitor
```

Open the serial monitor for the target environment:

```sh
/home/kurt/.platformio/penv/bin/platformio device monitor -e bluepill_f103c8_target
```

## Data Format

The controller serializes `k_uptime_get()` into 8 bytes using this layout:

```c
TX_i = (T_worker >> (56 - 8 * i)) & 0xFF
```

The target decodes the received buffer with the matching shift-and-OR loop, then prints both timestamps.

## Notes

- The app prints timestamps to the serial console on both sides.
- SPI is configured for 8-bit words and MSB-first transfers.
- The application keeps the role selection in the build configuration rather than in runtime arguments.