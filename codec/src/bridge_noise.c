/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "rng_bridge.h"
#include "../vendor/mbelib/src/core/mbe_adaptive.c"
void ad_rng_noise_get(ad_rng *s) { s->comfort = comfort_state; }
void ad_rng_noise_set(const ad_rng *s) { comfort_state = s->comfort; }
