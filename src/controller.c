#include <zephyr/devicetree.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "benchmark_shared.h"

#define CONTROLLER_SPI_NODE DT_NODELABEL(spi1)

#ifndef WORKER_CHILD_COUNT
#define WORKER_CHILD_COUNT 1U
#endif

static const struct device *const spi_dev = DEVICE_DT_GET(CONTROLLER_SPI_NODE);
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

	for (uint32_t cycle = 0U; cycle < EXPERIMENT_SYNC_CYCLES; cycle++) {
		const uint64_t controller_ts_us = get_hw_timestamp_us();

		encode_timestamp(controller_ts_us, tx_data);

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
			       (unsigned long long)(controller_ts_us / 1000U));
		}

		k_sleep(K_SECONDS(RESYNC_INTERVAL_SECONDS));
	}

	printk("worker: experiment complete (%u cycles)\n",
	       (unsigned int)EXPERIMENT_SYNC_CYCLES);
}