// SPDX-License-Identifier: GPL-3.0-or-later
#include "imbe_vocoder_impl.h"
#include "imbe_vocoder.h"
#include <mutex>
#include <cstring>
#include <new>
extern Flag Overflow,Carry;
UWord32 allmode_rand_get();void allmode_rand_set(UWord32);
static std::mutex gate;
struct Stream {imbe_vocoder *codec=nullptr;UWord32 random=1;Flag overflow=0,carry=0;};
struct Scope {
 Stream &s;UWord32 random;Flag overflow,carry;
 Scope(Stream &x):s(x),random(allmode_rand_get()),overflow(Overflow),carry(Carry){allmode_rand_set(s.random);Overflow=s.overflow;Carry=s.carry;}
 ~Scope(){s.random=allmode_rand_get();s.overflow=Overflow;s.carry=Carry;allmode_rand_set(random);Overflow=overflow;Carry=carry;}
};
extern "C" {
void *p25_create(){std::lock_guard<std::mutex> lock(gate);Stream *s=nullptr;try{s=new Stream;Scope context(*s);s->codec=new imbe_vocoder;return s;}catch(...){delete s;return nullptr;}}
void p25_destroy(void *p){std::lock_guard<std::mutex> lock(gate);auto s=static_cast<Stream*>(p);if(s){delete s->codec;delete s;}}
int p25_encode(void *p,const int16_t *pcm,int count,uint8_t *out,int size){
 if(out&&size==11)std::memset(out,0,11);
 if(!p||!pcm||!out||count!=160||size!=11)return -1;
 std::lock_guard<std::mutex> lock(gate);auto &s=*static_cast<Stream*>(p);Scope context(s);int16_t input[160];std::memcpy(input,pcm,320);s.codec->encode_4400(input,out);return 0;
}
int p25_decode(void *p,const uint8_t *in,int size,int16_t *pcm,int count){
 if(pcm&&count==160)std::memset(pcm,0,320);
 if(!p||!in||!pcm||size!=11||count!=160)return -1;
 // Reserved pitch values are erasures, not valid speech. Do not advance state.
 unsigned b0=(in[0]&0xfc)|((in[10]>>1)&3);if(b0>207)return 1;
 std::lock_guard<std::mutex> lock(gate);auto &s=*static_cast<Stream*>(p);Scope context(s);uint8_t input[11];std::memcpy(input,in,11);s.codec->decode_4400(pcm,input);return 0;
}
}
