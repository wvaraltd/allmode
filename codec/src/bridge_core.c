/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Pinned-source bridge: upstream file is preserved unchanged. */
#include "rng_bridge.h"
#include "allmode_dstar.h"
#include "../vendor/mbelib/src/core/mbelib.c"
void ad_rng_core_get(ad_rng *s) { s->rng = mbe_rng_state; }
void ad_rng_core_set(const ad_rng *s) { mbe_rng_state = s->rng; }
void ad_thread_cleanup(void) {
    mbe_fft_plan_free(mbe_fft_plan_instance);
    mbe_fft_plan_instance = NULL;
}
