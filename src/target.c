#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/irq.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <inttypes.h>
#include <stdbool.h>

#include "benchmark_shared.h"

#define TARGET_SPI_NODE DT_NODELABEL(spi1)
#define SYNC_PIN_NODE DT_NODELABEL(sync_trigger)

#ifndef CHILD_ID
#define CHILD_ID 0U
#endif

static const struct device *const spi_dev = DEVICE_DT_GET(TARGET_SPI_NODE);
static const struct gpio_dt_spec sync_pin = GPIO_DT_SPEC_GET(SYNC_PIN_NODE, gpios);
static const struct spi_config spi_config = {
	.frequency = 1000000U,
	.operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_SLAVE,
	.slave = 0U,
};

static struct gpio_callback sync_gpio_cb;
static volatile uint64_t last_sync_pulse_ts_us;
K_SEM_DEFINE(sync_pulse_sem, 0, 1);

static void sync_pulse_isr(const struct device *port,
				  struct gpio_callback *cb,
				  uint32_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	last_sync_pulse_ts_us = get_hw_timestamp_us();
	k_sem_give(&sync_pulse_sem);
}

void target_run(void)
{
	uint8_t tx_dummy[SPI_TIMESTAMP_BYTES] = {0};
	uint8_t rx_data[SPI_TIMESTAMP_BYTES];
	struct spi_buf tx_buf = {
		.buf = tx_dummy,
		.len = SPI_TIMESTAMP_BYTES,
	};
	struct spi_buf rx_buf = {
		.buf = rx_data,
		.len = SPI_TIMESTAMP_BYTES,
	};
	const struct spi_buf_set tx_set = {
		.buffers = &tx_buf,
		.count = 1U,
	};
	const struct spi_buf_set rx_set = {
		.buffers = &rx_buf,
		.count = 1U,
	};

	if (!device_is_ready(spi_dev)) {
		printk("child: SPI device is not ready\n");
		return;
	}

	if (!gpio_is_ready_dt(&sync_pin)) {
		printk("child: sync GPIO device is not ready\n");
		return;
	}

	if (gpio_pin_configure_dt(&sync_pin, GPIO_INPUT) < 0) {
		printk("child: failed to configure sync GPIO input\n");
		return;
	}

	if (gpio_pin_interrupt_configure_dt(&sync_pin, GPIO_INT_EDGE_TO_ACTIVE) < 0) {
		printk("child: failed to configure sync GPIO interrupt\n");
		return;
	}

	gpio_init_callback(&sync_gpio_cb, sync_pulse_isr, BIT(sync_pin.pin));
	if (gpio_add_callback(sync_pin.port, &sync_gpio_cb) < 0) {
		printk("child: failed to register sync GPIO callback\n");
		return;
	}

	printk("child: configured CHILD_ID=%d\n", CHILD_ID);

	bool have_reference = false;
	uint64_t ref_worker_ts_us = 0U;
	uint64_t ref_local_ts_us = 0U;

	for (uint32_t cycle = 0U; cycle < EXPERIMENT_SYNC_CYCLES; cycle++) {
		uint64_t controller_ts_us;
		uint64_t pulse_ts_us;
		uint64_t spi_rx_ts_us;
		uint64_t predicted_worker_ts_us;
		int64_t diff_us;
		int64_t spi_path_delay_us;
		int64_t synced_us;
		uint32_t synced_ms_int;
		uint32_t synced_ms_frac;
		int ret;
		unsigned int irq_key;

		k_sem_take(&sync_pulse_sem, K_FOREVER);
		irq_key = irq_lock();
		pulse_ts_us = last_sync_pulse_ts_us;
		irq_unlock(irq_key);

		ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);
		if (ret < 0) {
			printk("child: spi_transceive failed: %d\n", ret);
			continue;
		}

		spi_rx_ts_us = get_hw_timestamp_us();
		controller_ts_us = decode_timestamp(rx_data);
		spi_path_delay_us = (int64_t)spi_rx_ts_us - (int64_t)pulse_ts_us;

		if (!have_reference) {
			/* First sync establishes the local reference timeline. */
			diff_us = 0;
			have_reference = true;
		} else {
			predicted_worker_ts_us = ref_worker_ts_us + (pulse_ts_us - ref_local_ts_us);
			diff_us = (int64_t)predicted_worker_ts_us - (int64_t)controller_ts_us;
		}

		/* Re-anchor to the hardware-triggered timestamp, not the SPI receive time. */
		ref_worker_ts_us = controller_ts_us;
		ref_local_ts_us = pulse_ts_us;
		synced_us = (int64_t)controller_ts_us;
		if (synced_us < 0) {
			synced_us = 0;
		}
		synced_ms_int = (uint32_t)(synced_us / 1000LL);
		synced_ms_frac = (uint32_t)((synced_us % 1000LL) * 1000LL);

		printk("CHILD %d offset: %" PRId64
		       " us | pulse_to_spi: %" PRId64
		       " us | synced: %u.%06u ms\n",
		       CHILD_ID, diff_us, spi_path_delay_us, synced_ms_int, synced_ms_frac);
	}

	printk("child: experiment complete (%u cycles)\n",
	       (unsigned int)EXPERIMENT_SYNC_CYCLES);
}