# SPI Timestamp Exchange

This project contains a single Zephyr application with two build variants:

- controller (referred to as worker in the accompanying paper): sends its uptime timestamp over SPI
- target (referred to as child in the accompanying paper): receives and decodes the worker timestamp, then computes an offset so its reported uptime is aligned to the received worker timestamp

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
- `bluepill_f103c8_jitter_controller`
- `bluepill_f103c8_jitter_target`
- `bluepill_f103c8_mco_hse`
- `bluepill_f103c8_mco_sysclk`

The controller environment is the default build.

Use `platformio` from your shell path.

## Build Commands

Build the default controller (worker) image:

```sh
platformio run
```

Build the worker with a custom number of children (same timestamp sent sequentially to each child per sync cycle):

```sh
env PLATFORMIO_BUILD_FLAGS="-DWORKER_CHILD_COUNT=2" platformio run -e bluepill_f103c8_controller
```

Build the target (child) image:

```sh
platformio run -e bluepill_f103c8_target
```

Build the target with a custom child ID:

```sh
env PLATFORMIO_BUILD_FLAGS="-DCHILD_ID=2" platformio run -e bluepill_f103c8_target
```

Build the target with a custom main-thread priority:

```sh
platformio run -e bluepill_f103c8_target_prio1
```

`CONFIG_MAIN_THREAD_PRIORITY` is a Zephyr Kconfig option, so it must be set in a Zephyr `.conf` fragment rather than via `PLATFORMIO_BUILD_FLAGS`. The example environment above includes [zephyr/target_prio1.conf](zephyr/target_prio1.conf).

Build and upload the target with a custom child ID (recommended):

```sh
env PLATFORMIO_BUILD_FLAGS="-DCHILD_ID=2" platformio run -e bluepill_f103c8_target -t upload
```

## Clock Line Jitter Builds

Use the dedicated continuous-transfer environments below when you want the SPI clock to run indefinitely for oscilloscope-based clock-line jitter measurements.

Build the continuous SPI master source:

```sh
platformio run -e bluepill_f103c8_jitter_controller
```

Build the continuous SPI slave sink:

```sh
platformio run -e bluepill_f103c8_jitter_target
```

Build and upload the continuous SPI master source:

```sh
platformio run -e bluepill_f103c8_jitter_controller -t upload
```

Build and upload the continuous SPI slave sink:

```sh
platformio run -e bluepill_f103c8_jitter_target -t upload
```

Build the continuous SPI master source with a custom clock frequency, for example 2 MHz:

```sh
env PLATFORMIO_BUILD_FLAGS="-DJITTER_SPI_FREQUENCY_HZ=2000000" platformio run -e bluepill_f103c8_jitter_controller
```

Build and upload the continuous SPI master source with a custom clock frequency, for example 2 MHz:

```sh
env PLATFORMIO_BUILD_FLAGS="-DJITTER_SPI_FREQUENCY_HZ=2000000" platformio run -e bluepill_f103c8_jitter_controller -t upload
```

Build and upload the matching continuous SPI slave sink with the same custom clock frequency:

```sh
env PLATFORMIO_BUILD_FLAGS="-DJITTER_SPI_FREQUENCY_HZ=2000000" platformio run -e bluepill_f103c8_jitter_target -t upload
```

Keep `JITTER_SPI_FREQUENCY_HZ` identical on both jitter environments.

## Clock Probe Builds (MCO on PA8)

Use the MCO environments when you want to observe a clock directly on PA8 with an oscilloscope without probing the crystal network itself.

Build MCO output of HSE on PA8:

```sh
platformio run -e bluepill_f103c8_mco_hse
```

Build MCO output of SYSCLK on PA8:

```sh
platformio run -e bluepill_f103c8_mco_sysclk
```

Build and upload either MCO image:

```sh
platformio run -e bluepill_f103c8_mco_hse -t upload
platformio run -e bluepill_f103c8_mco_sysclk -t upload
```

Measure PA8 directly on the MCU pin/header. PA8 is a push-pull digital output in this mode.

## Load Testing Builds

The project supports two operational build profiles:

- idle: synthetic load disabled
- stressed: synthetic load enabled with a high-priority dummy thread

Build controller (idle):

```sh
platformio run -e bluepill_f103c8_controller
```

Build target (idle):

```sh
platformio run -e bluepill_f103c8_target
```

Build controller (stressed):

```sh
env PLATFORMIO_BUILD_FLAGS="-DCONFIG_SYNTHETIC_LOAD_TEST=1 -DCONFIG_SYNTHETIC_LOAD_STACKSIZE=1024 -DCONFIG_SYNTHETIC_LOAD_PRIORITY=5 -DCONFIG_SYNTHETIC_LOAD_LOOP_ITERS=100000 -DCONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US=100 -DWORKER_CHILD_COUNT=2" platformio run -e bluepill_f103c8_controller
```

Build target (stressed):

```sh
env PLATFORMIO_BUILD_FLAGS="-DCONFIG_SYNTHETIC_LOAD_TEST=1 -DCONFIG_SYNTHETIC_LOAD_STACKSIZE=1024 -DCONFIG_SYNTHETIC_LOAD_PRIORITY=5 -DCONFIG_SYNTHETIC_LOAD_LOOP_ITERS=100000 -DCONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US=100 -DCHILD_ID=1" platformio run -e bluepill_f103c8_target
```

Build and upload stressed images:

```sh
env PLATFORMIO_BUILD_FLAGS="-DCONFIG_SYNTHETIC_LOAD_TEST=1 -DCONFIG_SYNTHETIC_LOAD_STACKSIZE=1024 -DCONFIG_SYNTHETIC_LOAD_PRIORITY=5 -DCONFIG_SYNTHETIC_LOAD_LOOP_ITERS=100000 -DCONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US=100 -DWORKER_CHILD_COUNT=2" platformio run -e bluepill_f103c8_controller -t upload
env PLATFORMIO_BUILD_FLAGS="-DCONFIG_SYNTHETIC_LOAD_TEST=1 -DCONFIG_SYNTHETIC_LOAD_STACKSIZE=1024 -DCONFIG_SYNTHETIC_LOAD_PRIORITY=5 -DCONFIG_SYNTHETIC_LOAD_LOOP_ITERS=100000 -DCONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US=100 -DCHILD_ID=1" platformio run -e bluepill_f103c8_target -t upload
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

Flash the MCO HSE clock-probe build:

```sh
platformio run -e bluepill_f103c8_mco_hse -t upload
```

Flash the MCO SYSCLK clock-probe build:

```sh
platformio run -e bluepill_f103c8_mco_sysclk -t upload
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

## Child Log Capture

Collect child output directly to a file with picocom:

```sh
picocom -b 115200 -g child0.log /dev/ttyUSB0
```

## Metrics Script

Use the Python script below to compute drift offset, precision, and SPI transaction jitter from child output logs:

```sh
python3 scripts/calc_metrics.py child0.log child1.log --json-out metrics.json
```

Notes:
- Input lines must match the child log format: `CHILD <id> offset: <us> us | synced: <ms>.<frac> ms`.
- Clock line jitter is reported as unavailable from software logs (it requires oscilloscope edge timing data).

## Chart Generation

Generate charts from the versioned metrics files in `metrics/`.

Drift offset boxplot (normal metrics):

```sh
python3 scripts/offset_boxplot.py
```

SPI jitter bar chart (normal metrics):

```sh
python3 scripts/jitter_barchart.py
```

Under-load mode (uses `metrics_load_V1.json` ... `metrics_load_V4.json`, adds load heading, and writes `_load` output filenames):

```sh
python3 scripts/offset_boxplot.py --under-load
python3 scripts/jitter_barchart.py --under-load
```

Custom under-load heading text:

```sh
python3 scripts/offset_boxplot.py --under-load --load-heading "Under Load: custom parameters"
python3 scripts/jitter_barchart.py --under-load --load-heading "Under Load: custom parameters"
```

Custom output basename (without extension):

```sh
python3 scripts/offset_boxplot.py --output-stem drift_offset_custom
python3 scripts/jitter_barchart.py --output-stem spi_jitter_custom
```

The scripts always export both `.svg` and `.pdf` files.

## Data Format

The controller serializes `k_uptime_get()` into 8 bytes using this layout:

```c
TX_i = (T_worker >> (56 - 8 * i)) & 0xFF
```

The target decodes the received buffer with the matching shift-and-OR loop, computes a local offset, and reports an adjusted uptime aligned to the received worker timestamp.

## Notes

- The app prints timestamps to the serial console on both sides.
- SPI is configured for 8-bit words and MSB-first transfers.
- The implementation intentionally keeps application data flow one-way (worker -> child) while still using `spi_transceive()` on both nodes.
- The worker sends the same timestamp in succession to each configured child every sync cycle (`WORKER_CHILD_COUNT`, default fallback: 1 in code).
- The child adjusts its reported uptime to the received worker timestamp using a per-sync offset (`worker_ts - local_ts`).
- The worker resynchronization interval is 15 seconds.
- Each experiment runs for 240 sync cycles, so nominal duration is 3600 seconds (1 hour).
- `CHILD_ID` is a compile-time option (default fallback: 1 in code). Override per build with `PLATFORMIO_BUILD_FLAGS`.
- The application keeps the role selection in the build configuration rather than in runtime arguments.