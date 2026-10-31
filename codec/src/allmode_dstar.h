/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ALLMODE_DSTAR_H
#define ALLMODE_DSTAR_H
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
typedef struct ad_stream ad_stream;
typedef struct { int errors; unsigned flags; } ad_result;
enum { AD_OK=0, AD_INVALID=-1, AD_CODEC=-2, AD_CONCEALED=1 };
/* Own one context per duplex stream. No concurrent calls on the same context.
 * Independent contexts may be interleaved or run on separate threads.
 * PCM is exactly 160 signed 16-bit samples at 8000 Hz; payload exactly 9 bytes.
 * No network, radio header, slow data, sync cadence, or transmission is provided.
 * A failed encode clears a valid output buffer; NEVER transmit it on failure.
 * Invalid decode or explicit loss returns silence without advancing history.
 * Codec-detected errors use upstream concealment; inspect result flags/errors.
 */
AD_API ad_stream *ad_create(uint32_t seed);
AD_API void ad_destroy(ad_stream *s);
AD_API int ad_reset(ad_stream *s, uint32_t seed);
AD_API int ad_encode(ad_stream *s, const int16_t *pcm, size_t samples,
                     uint8_t *payload, size_t bytes);
AD_API int ad_decode(ad_stream *s, const uint8_t *payload, size_t bytes,
                     int16_t *pcm, size_t samples, ad_result *result);
AD_API int ad_lost(ad_stream *s, int16_t *pcm, size_t samples);
/* Call on a worker thread when finished with ALL mbelib work on that thread. */
AD_API void ad_thread_cleanup(void);
#ifdef __cplusplus
}
#endif
#endif
