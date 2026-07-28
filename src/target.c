#include <zephyr/devicetree.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "benchmark_shared.h"

#define TARGET_SPI_NODE DT_NODELABEL(spi1)

static const struct device *const spi_dev = DEVICE_DT_GET(TARGET_SPI_NODE);
static const struct spi_config spi_config = {
	.frequency = 1000000U,
	.operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_SLAVE,
	.slave = 0U,
};

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

	for (uint32_t cycle = 0U; cycle < EXPERIMENT_SYNC_CYCLES; cycle++) {
		uint64_t controller_ts;
		uint64_t target_ts;
		int64_t uptime_offset_ms;
		int64_t adjusted_target_ts;
		int ret;

		ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);
		if (ret < 0) {
			printk("child: spi_transceive failed: %d\n", ret);
			continue;
		}

		target_ts = (uint64_t)k_uptime_get();
		controller_ts = decode_timestamp(rx_data);
		uptime_offset_ms = (int64_t)controller_ts - (int64_t)target_ts;
		adjusted_target_ts = (int64_t)target_ts + uptime_offset_ms;

		printk("child: rx_worker=%llu ms local=%llu ms adjusted=%lld ms offset=%lld ms\n",
		       (unsigned long long)controller_ts,
		       (unsigned long long)target_ts,
		       (long long)adjusted_target_ts,
		       (long long)uptime_offset_ms);
	}

	printk("child: experiment complete (%u cycles)\n",
	       (unsigned int)EXPERIMENT_SYNC_CYCLES);
}