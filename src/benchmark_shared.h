#ifndef BENCHMARK_SHARED_H
#define BENCHMARK_SHARED_H

#include <stdint.h>

#define SPI_TIMESTAMP_BYTES 8U

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