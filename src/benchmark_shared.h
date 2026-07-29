#ifndef BENCHMARK_SHARED_H
#define BENCHMARK_SHARED_H

#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys_clock.h>

#define SPI_TIMESTAMP_BYTES 8U
#define RESYNC_INTERVAL_SECONDS 15U
#define EXPERIMENT_SYNC_CYCLES 240U
#define SYNC_PULSE_WIDTH_US 200U

static inline uint64_t get_hw_timestamp_us(void)
{
	return (uint64_t)((uint64_t)k_cycle_get_64() * 1000000ULL /
			 sys_clock_hw_cycles_per_sec());
}

static inline void encode_timestamp(uint64_t timestamp, uint8_t *buffer)
{
	for (int i = 0; i < 8; i++) {
		buffer[i] = (timestamp >> (56 - (8 * i))) & 0xFF;
	}
}

static inline uint64_t decode_timestamp(const uint8_t *buffer)
{
	uint64_t timestamp = 0U;

	for (int i = 0; i < 8; i++) {
		timestamp = (timestamp << 8) | buffer[i];
	}

	return timestamp;
}

#endif /* BENCHMARK_SHARED_H */