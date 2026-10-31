/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "allmode_dstar.h"
#include "rng_bridge.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <mbelib-neo/mbelib.h>
typedef char short_must_be_16_bits[(sizeof(short)==2 && SHRT_MAX==32767) ? 1 : -1];
struct ad_stream {
    mbe_ambe2400_encoder *encoder;
    mbe_parms ec, ep, ee, dc, dp, de;
    ad_rng noise;
};
static void rng_get(ad_rng *s) { ad_rng_core_get(s); ad_rng_noise_get(s); ad_rng_fft_get(s); }
static void rng_set(const ad_rng *s) { ad_rng_core_set(s); ad_rng_noise_set(s); ad_rng_fft_set(s); }
int ad_reset(ad_stream *s, uint32_t seed) {
    ad_rng saved;
    if (!s) return AD_INVALID;
    mbe_ambe2400EncoderReset(s->encoder);
    mbe_initMbeParms(&s->ec, &s->ep, &s->ee);
    mbe_initMbeParms(&s->dc, &s->dp, &s->de);
    rng_get(&saved);
    mbe_setThreadRngSeed(seed);
    rng_get(&s->noise);
    rng_set(&saved);
    return AD_OK;
}
ad_stream *ad_create(uint32_t seed) {
    ad_stream *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->encoder = mbe_ambe2400EncoderAlloc();
    if (!s->encoder) { free(s); return NULL; }
    ad_reset(s, seed);
    return s;
}
void ad_destroy(ad_stream *s) {
    if (s) { mbe_ambe2400EncoderFree(s->encoder); free(s); }
}
int ad_encode(ad_stream *s, const int16_t *pcm, size_t samples, uint8_t *payload, size_t bytes) {
    char bits[49], frame[4][24];
    short input[160];
    if (payload && bytes==9) memset(payload, 0, 9);
    if (!s || !pcm || !payload || samples!=160 || bytes!=9) return AD_INVALID;
    for (int i=0; i<160; ++i) input[i]=pcm[i];
    if (mbe_encodeAmbe2400ParmsShort(s->encoder,input,bits,&s->ec,&s->ep)<0 ||
        mbe_encodeAmbe3600x2400Frame(bits,frame)<0 ||
        mbe_encodeDStarDVData((const char (*)[24])frame,payload)<0) return AD_CODEC;
    mbe_moveMbeParms(&s->ec,&s->ep);
    return AD_OK;
}
int ad_decode(ad_stream *s, const uint8_t *payload, size_t bytes, int16_t *pcm, size_t samples, ad_result *result) {
    char bits[49], frame[4][24];
    short output[160];
    mbe_process_result r;
    ad_rng saved;
    if (pcm && samples==160) memset(pcm,0,160*sizeof(*pcm));
    if (result) memset(result,0,sizeof(*result));
    if (!s || !payload || !pcm || bytes!=9 || samples!=160) return AD_INVALID;
    if (mbe_decodeDStarDVData(payload,frame)<0) return AD_CODEC;
    rng_get(&saved); rng_set(&s->noise);
    int rc=mbe_processAmbe3600x2400Frame(output,&r,(const char (*)[24])frame,bits,&s->dc,&s->dp,&s->de);
    rng_get(&s->noise); rng_set(&saved);
    if (rc<0) return AD_CODEC;
    for (int i=0; i<160; ++i) pcm[i]=output[i];
    if (result) { result->errors=r.total_errors; result->flags=r.flags; }
    return AD_OK;
}
int ad_lost(ad_stream *s, int16_t *pcm, size_t samples) {
    if (!s || !pcm || samples!=160) return AD_INVALID;
    memset(pcm,0,160*sizeof(*pcm));
    return AD_CONCEALED;
}
