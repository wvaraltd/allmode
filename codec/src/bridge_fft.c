/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "rng_bridge.h"
#include "../vendor/mbelib/src/core/mbe_unvoiced_fft.c"
void ad_rng_fft_get(ad_rng *s) { s->pending = pending_noise_seed; s->has_pending = noise_seed_pending; }
void ad_rng_fft_set(const ad_rng *s) { pending_noise_seed = s->pending; noise_seed_pending = s->has_pending; }
