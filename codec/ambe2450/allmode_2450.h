/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ALLMODE_2450_H
#define ALLMODE_2450_H
#include <stddef.h>
#include <stdint.h>
#ifdef _WIN32
#define AD_API __declspec(dllexport)
#else
#define AD_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
typedef struct a2450_stream a2450_stream;
typedef struct { int errors; unsigned flags; } a2450_result;
enum { AD_OK=0, AD_INVALID=-1, AD_CODEC=-2, AD_CONCEALED=1 };
/* Own one context per duplex stream. No concurrent calls on the same context.
 * Independent contexts may be interleaved or run on separate threads.
 * PCM is exactly 160 signed 16-bit samples at 8000 Hz; payload exactly 9 bytes.
 * No network, radio header, slow data, sync cadence, or transmission is provided.
 * A failed encode clears a valid output buffer; NEVER transmit it on failure.
 * Invalid decode or explicit loss returns silence without advancing history.
 * Codec-detected errors use upstream concealment; inspect result flags/errors.
 */
AD_API a2450_stream *a2450_create(uint32_t seed);
AD_API void a2450_destroy(a2450_stream *s);
AD_API int a2450_reset(a2450_stream *s, uint32_t seed);
AD_API int a2450_encode(a2450_stream *s, const int16_t *pcm, size_t samples,
                     uint8_t *payload, size_t bytes);
AD_API int a2450_decode(a2450_stream *s, const uint8_t *payload, size_t bytes,
                     int16_t *pcm, size_t samples, a2450_result *result);
AD_API int a2450_lost(a2450_stream *s, int16_t *pcm, size_t samples);
/* Call on a worker thread when finished with ALL mbelib work on that thread. */
AD_API void ad_thread_cleanup(void);
#ifdef __cplusplus
}
#endif
#endif
