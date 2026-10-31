/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef AD_RNG_BRIDGE_H
#define AD_RNG_BRIDGE_H
#include <stdint.h>
typedef struct { uint32_t rng, pending; int has_pending; uint64_t comfort; } ad_rng;
void ad_rng_core_get(ad_rng *s);
void ad_rng_core_set(const ad_rng *s);
void ad_rng_noise_get(ad_rng *s);
void ad_rng_noise_set(const ad_rng *s);
void ad_rng_fft_get(ad_rng *s);
void ad_rng_fft_set(const ad_rng *s);
#endif
