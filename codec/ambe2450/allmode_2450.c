/* DMR bit schedule attribution: Mike Zingman N4IRR, HBLink-org/dmr_utils3. */
/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "allmode_2450.h"
#include "rng_bridge.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <mbelib-neo/mbelib.h>

static const unsigned W[36]={0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,2,0,2,0,2,0,2,0,2,0,2,0,2};
static const unsigned X[36]={23,10,22,9,21,8,20,7,19,6,18,5,17,4,16,3,15,2,14,1,13,0,12,10,11,9,10,8,9,7,8,6,7,5,6,4};
static const unsigned Y[36]={0,2,0,2,0,2,0,2,0,3,0,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3};
static const unsigned Z[36]={5,3,4,2,3,1,2,0,1,13,0,12,22,11,21,10,20,9,19,8,18,7,17,6,16,5,15,4,14,3,13,2,12,1,11,0};
static void pack(const char f[4][24],uint8_t p[9]) {
 memset(p,0,9);
 for(unsigned i=0;i<36;i++){
  unsigned b=2*i;
  p[b/8]|=(f[W[i]][X[i]]&1)<<(7-b%8);b++;
  p[b/8]|=(f[Y[i]][Z[i]]&1)<<(7-b%8);
 }
}
static void unpack(const uint8_t p[9],char f[4][24]) {
 memset(f,0,96);
 for(unsigned i=0;i<36;i++){
  unsigned b=2*i;
  f[W[i]][X[i]]=(p[b/8]>>(7-b%8))&1;b++;
  f[Y[i]][Z[i]]=(p[b/8]>>(7-b%8))&1;
 }
}

typedef char short_must_be_16_bits[(sizeof(short)==2 && SHRT_MAX==32767) ? 1 : -1];
struct a2450_stream {
    mbe_ambe2450_encoder *encoder;
    mbe_parms ec, ep, ee, dc, dp, de;
    ad_rng noise;
};
static void rng_get(ad_rng *s) { ad_rng_core_get(s); ad_rng_noise_get(s); ad_rng_fft_get(s); }
static void rng_set(const ad_rng *s) { ad_rng_core_set(s); ad_rng_noise_set(s); ad_rng_fft_set(s); }
int a2450_reset(a2450_stream *s, uint32_t seed) {
    ad_rng saved;
    if (!s) return AD_INVALID;
    mbe_ambe2450EncoderReset(s->encoder);
    mbe_initMbeParms(&s->ec, &s->ep, &s->ee);
    mbe_initMbeParms(&s->dc, &s->dp, &s->de);
    rng_get(&saved);
    mbe_setThreadRngSeed(seed);
    rng_get(&s->noise);
    rng_set(&saved);
    return AD_OK;
}
a2450_stream *a2450_create(uint32_t seed) {
    a2450_stream *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->encoder = mbe_ambe2450EncoderAlloc();
    if (!s->encoder) { free(s); return NULL; }
    a2450_reset(s, seed);
    return s;
}
void a2450_destroy(a2450_stream *s) {
    if (s) { mbe_ambe2450EncoderFree(s->encoder); free(s); }
}
int a2450_encode(a2450_stream *s, const int16_t *pcm, size_t samples, uint8_t *payload, size_t bytes) {
    char bits[49], frame[4][24];
    short input[160];
    if (payload && bytes==9) memset(payload, 0, 9);
    if (!s || !pcm || !payload || samples!=160 || bytes!=9) return AD_INVALID;
    for (int i=0; i<160; ++i) input[i]=pcm[i];
    if (mbe_encodeAmbe2450ParmsShort(s->encoder,input,bits,&s->ec,&s->ep)<0 ||
        mbe_encodeAmbe3600x2450Frame(bits,frame)<0) return AD_CODEC;
    pack((const char (*)[24])frame,payload);
    mbe_moveMbeParms(&s->ec,&s->ep);
    return AD_OK;
}
int a2450_decode(a2450_stream *s, const uint8_t *payload, size_t bytes, int16_t *pcm, size_t samples, a2450_result *result) {
    char bits[49], frame[4][24];
    short output[160];
    mbe_process_result r;
    ad_rng saved;
    if (pcm && samples==160) memset(pcm,0,160*sizeof(*pcm));
    if (result) memset(result,0,sizeof(*result));
    if (!s || !payload || !pcm || bytes!=9 || samples!=160) return AD_INVALID;
    unpack(payload,frame);
    rng_get(&saved); rng_set(&s->noise);
    int rc=mbe_processAmbe3600x2450Frame(output,&r,(const char (*)[24])frame,bits,&s->dc,&s->dp,&s->de);
    rng_get(&s->noise); rng_set(&saved);
    if (rc<0) return AD_CODEC;
    for (int i=0; i<160; ++i) pcm[i]=output[i];
    if (result) { result->errors=r.total_errors; result->flags=r.flags; }
    return AD_OK;
}
int a2450_lost(a2450_stream *s, int16_t *pcm, size_t samples) {
    if (!s || !pcm || samples!=160) return AD_INVALID;
    memset(pcm,0,160*sizeof(*pcm));
    return AD_CONCEALED;
}
