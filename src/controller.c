#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "benchmark_shared.h"

#define CONTROLLER_SPI_NODE DT_NODELABEL(spi1)
#define SYNC_PIN_NODE DT_ALIAS(sync_out)

#ifndef WORKER_CHILD_COUNT
#define WORKER_CHILD_COUNT 1U
#endif

static const struct device *const spi_dev = DEVICE_DT_GET(CONTROLLER_SPI_NODE);
static const struct gpio_dt_spec sync_pin = GPIO_DT_SPEC_GET(SYNC_PIN_NODE, gpios);
static const struct spi_config spi_config = {
	.frequency = 1000000U,
	.operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_MASTER,
};

void controller_run(void)
{
	uint8_t tx_data[SPI_TIMESTAMP_BYTES];
	uint8_t rx_discard[SPI_TIMESTAMP_BYTES];
	struct spi_buf tx_buf = {
		.buf = tx_data,
		.len = SPI_TIMESTAMP_BYTES,
	};
	struct spi_buf rx_buf = {
		.buf = rx_discard,
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
		printk("worker: SPI device is not ready\n");
		return;
	}

	if (!gpio_is_ready_dt(&sync_pin)) {
		printk("worker: sync GPIO device is not ready\n");
		return;
	}

	if (gpio_pin_configure_dt(&sync_pin, GPIO_OUTPUT_INACTIVE) < 0) {
		printk("worker: failed to configure sync GPIO\n");
		return;
	}

	for (uint32_t cycle = 0U; cycle < EXPERIMENT_SYNC_CYCLES; cycle++) {
		const uint64_t controller_ts_us = get_hw_timestamp_us();
		int pulse_ret;

		encode_timestamp(controller_ts_us, tx_data);

		pulse_ret = gpio_pin_set_dt(&sync_pin, 1);
		if (pulse_ret < 0) {
			printk("worker: failed to set sync pulse high: %d\n", pulse_ret);
			continue;
		}
		k_busy_wait(SYNC_PULSE_WIDTH_US);
		pulse_ret = gpio_pin_set_dt(&sync_pin, 0);
		if (pulse_ret < 0) {
			printk("worker: failed to set sync pulse low: %d\n", pulse_ret);
			continue;
		}

		for (uint32_t child = 0U; child < WORKER_CHILD_COUNT; child++) {
			int ret;

			ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);
			if (ret < 0) {
				printk("worker: child=%u spi_transceive failed: %d\n",
				       (unsigned int)(child), ret);
				k_sleep(K_MSEC(250));
				continue;
			}

			printk("worker: child=%u tx=%llu ms\n",
			       (unsigned int)(child),
			       (unsigned long long)(controller_ts_us / 1000ULL));
		}

		k_sleep(K_SECONDS(RESYNC_INTERVAL_SECONDS));
	}

	printk("worker: experiment complete (%u cycles)\n",
	       (unsigned int)EXPERIMENT_SYNC_CYCLES);
}