from pathlib import Path
R=Path(__file__).resolve().parent
names=['ad_stream','ad_result','ad_create','ad_destroy','ad_reset','ad_encode','ad_decode','ad_lost']
def rename(s):
 for n in names:s=s.replace(n,n.replace('ad_','a2450_'))
 return s.replace('ALLMODE_DSTAR_H','ALLMODE_2450_H').replace('allmode_dstar.h','allmode_2450.h').replace('2400','2450')
h=rename((R.parent/'src/allmode_dstar.h').read_text())
s=rename((R.parent/'src/allmode_dstar.c').read_text())
# DMR interleave schedule documented by HBLink-org/dmr_utils3 ambe_utils.py
# (Mike Zingman N4IRR, GPL-3.0-or-later). This adapter follows that schedule;
# quantization/FEC remains in the pinned mbelib source, not firmware.
schedule='''
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
'''
s=s.replace('typedef char short_must',schedule+'\ntypedef char short_must')
s=s.replace('mbe_encodeAmbe3600x2450Frame(bits,frame)<0 ||\n        mbe_encodeDStarDVData((const char (*)[24])frame,payload)<0)', 'mbe_encodeAmbe3600x2450Frame(bits,frame)<0)')
s=s.replace('    mbe_moveMbeParms(&s->ec,&s->ep);','    pack((const char (*)[24])frame,payload);\n    mbe_moveMbeParms(&s->ec,&s->ep);')
s=s.replace('    if (mbe_decodeDStarDVData(payload,frame)<0) return AD_CODEC;','    unpack(payload,frame);')
s=s.replace('GPL-2.0-or-later','GPL-3.0-or-later')
s='/* DMR bit schedule attribution: Mike Zingman N4IRR, HBLink-org/dmr_utils3. */\n'+s
(R/'allmode_2450.h').write_text(h)
(R/'allmode_2450.c').write_text(s)
print('Generated independent per-stream AMBE2450 wrapper with DMR 72-bit packing')
