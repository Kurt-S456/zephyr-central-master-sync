#include <zephyr/devicetree.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <string.h>

#define JITTER_SPI_NODE DT_NODELABEL(spi1)
#define JITTER_TRANSFER_BYTES 64U

#ifndef JITTER_SPI_FREQUENCY_HZ
#define JITTER_SPI_FREQUENCY_HZ 1000000U
#endif

static const struct device *const spi_dev = DEVICE_DT_GET(JITTER_SPI_NODE);

void jitter_controller_run(void)
{
	static uint8_t tx_data[JITTER_TRANSFER_BYTES];
	static uint8_t rx_discard[JITTER_TRANSFER_BYTES];
	struct spi_buf tx_buf = {
		.buf = tx_data,
		.len = sizeof(tx_data),
	};
	struct spi_buf rx_buf = {
		.buf = rx_discard,
		.len = sizeof(rx_discard),
	};
	const struct spi_buf_set tx_set = {
		.buffers = &tx_buf,
		.count = 1U,
	};
	const struct spi_buf_set rx_set = {
		.buffers = &rx_buf,
		.count = 1U,
	};
	const struct spi_config spi_config = {
		.frequency = JITTER_SPI_FREQUENCY_HZ,
		.operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_MASTER,
	};

	if (!device_is_ready(spi_dev)) {
		printk("jitter-controller: SPI device is not ready\n");
		return;
	}

	memset(tx_data, 0xAA, sizeof(tx_data));
	printk("jitter-controller: streaming %u-byte SPI transfers continuously at %u Hz\n",
	       (unsigned int)sizeof(tx_data),
	       (unsigned int)JITTER_SPI_FREQUENCY_HZ);

	while (1) {
		int ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);

		if (ret < 0) {
			printk("jitter-controller: spi_transceive failed: %d\n", ret);
			k_sleep(K_MSEC(100));
		}
	}
}

void jitter_target_run(void)
{
	static uint8_t tx_dummy[JITTER_TRANSFER_BYTES];
	static uint8_t rx_data[JITTER_TRANSFER_BYTES];
	struct spi_buf tx_buf = {
		.buf = tx_dummy,
		.len = sizeof(tx_dummy),
	};
	struct spi_buf rx_buf = {
		.buf = rx_data,
		.len = sizeof(rx_data),
	};
	const struct spi_buf_set tx_set = {
		.buffers = &tx_buf,
		.count = 1U,
	};
	const struct spi_buf_set rx_set = {
		.buffers = &rx_buf,
		.count = 1U,
	};
	const struct spi_config spi_config = {
		.frequency = JITTER_SPI_FREQUENCY_HZ,
		.operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_SLAVE,
		.slave = 0U,
	};

	if (!device_is_ready(spi_dev)) {
		printk("jitter-target: SPI device is not ready\n");
		return;
	}

	memset(tx_dummy, 0x00, sizeof(tx_dummy));
	printk("jitter-target: ready for continuous SPI transfers at %u Hz\n",
	       (unsigned int)JITTER_SPI_FREQUENCY_HZ);

	while (1) {
		int ret = spi_transceive(spi_dev, &spi_config, &tx_set, &rx_set);

		if (ret < 0) {
			printk("jitter-target: spi_transceive failed: %d\n", ret);
			k_sleep(K_MSEC(100));
		}
	}
}