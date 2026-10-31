/* SPDX-License-Identifier: GPL-3.0-or-later
 * Thin bounded ABI around pinned G4KLX FICH/convolution/CRC implementations. */
#include "YSFFICH.h"
#include "YSFConvolution.h"
#include "CRC.h"
#include <cstdint>
#include <cstring>
static unsigned bit(const uint8_t *p,unsigned i){return (p[i/8]>>(7-i%8))&1;}
static void put(uint8_t *p,unsigned i,unsigned v){p[i/8]=(p[i/8]&~(128>>(i%8)))|(v<<(7-i%8));}
static const uint8_t white[20]={0x93,0xd7,0x51,0x21,0x9c,0x2f,0x6c,0xd0,0xef,0x0f,0xf8,0x3d,0xf1,0x73,0x20,0x94,0xed,0x1e,0x7c,0xd8};
extern "C" {
int ysf_fich_encode(const uint8_t *raw,unsigned size,uint8_t *out,unsigned length){
 if(!raw||!out||size!=4||length!=25)return -1;
 uint8_t data[120]={0},f[6]={0};memcpy(f,raw,4);CYSFFICH fich;fich.setRaw(f);fich.encode(data);memcpy(out,data+5,25);return 0;
}
int ysf_fich_decode(const uint8_t *in,unsigned length,uint8_t *raw,unsigned size){
 if(!raw||!in||size!=4||length!=25)return -1;
 uint8_t data[120]={0},f[6]={0};memcpy(data+5,in,25);CYSFFICH fich;if(!fich.decode(data))return -2;fich.getRaw(f);memcpy(raw,f,4);return 0;
}
int ysf_data_encode(const uint8_t *in,unsigned length,uint8_t *out,unsigned size){
 if(!in||!out||(length!=10&&length!=20)||size!=(length==10?25u:45u))return -1;
 uint8_t data[23]={0},encoded[45]={0};for(unsigned i=0;i<length;i++)data[i]=in[i]^white[i];
 CCRC::addCCITT16(data,length+2);CYSFConvolution conv;unsigned pairs=size*4;conv.encode(data,encoded,pairs);memset(out,0,size);
 unsigned columns=length==10?5:9;
 for(unsigned i=0;i<pairs;i++){unsigned n=(i%columns)*40+(i/columns)*2;put(out,n,bit(encoded,2*i));put(out,n+1,bit(encoded,2*i+1));}return 0;
}
int ysf_data_decode(const uint8_t *in,unsigned size,uint8_t *out,unsigned length){
 if(!in||!out||(length!=10&&length!=20)||size!=(length==10?25u:45u))return -1;
 CYSFConvolution conv;conv.start();unsigned columns=length==10?5:9;
 for(unsigned i=0;i<size*4;i++){unsigned n=(i%columns)*40+(i/columns)*2;conv.decode(bit(in,n),bit(in,n+1));}
 uint8_t data[23]={0};conv.chainback(data,(length+2)*8);if(!CCRC::checkCCITT16(data,length+2))return -2;
 for(unsigned i=0;i<length;i++)out[i]=data[i]^white[i];
 return 0;
}
}
