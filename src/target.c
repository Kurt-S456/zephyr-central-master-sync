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
	uint8_t tx_data[SPI_TIMESTAMP_BYTES];
	uint8_t rx_data[SPI_TIMESTAMP_BYTES];
	struct spi_buf tx_buf = {
		.buf = tx_data,
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
		printk("target: SPI device is not ready\n");
		return;
	}

	while (1) {
		const uint64_t target_ts = (uint64_t)k_uptime_get();
		uint64_t controller_ts;
		int ret;

		encode_timestamp(target_ts, tx_data);
		ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);
		if (ret < 0) {
			printk("target: spi_transceive failed: %d\n", ret);
			continue;
		}

		controller_ts = decode_timestamp(rx_data);
		printk("target: tx=%llu ms rx=%llu ms frames=%d\n",
		       (unsigned long long)target_ts,
		       (unsigned long long)controller_ts,
		       ret);
	}
}