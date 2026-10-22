// Small C ABI adapter for DroidStar's published Vocoder interface.
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
class Vocoder {
public:
 virtual ~Vocoder() {}
 virtual void decode_2400x1200(int16_t*,uint8_t*)=0;
 virtual void decode_2450x1150(int16_t*,uint8_t*)=0;
 virtual void decode_2450(int16_t*,uint8_t*)=0;
 virtual void encode_2400x1200(int16_t*,uint8_t*)=0;
 virtual void encode_2450x1150(int16_t*,uint8_t*)=0;
 virtual void encode_2450(int16_t*,uint8_t*)=0;
};
struct Codec {void* library;Vocoder* encoder;Vocoder* decoder;void(*destroy)(Vocoder*);};
extern "C" void* allmode_codec_open(const char* path) {
 void* library=dlopen(path,RTLD_NOW|RTLD_LOCAL);if(!library)return nullptr;
 auto create=reinterpret_cast<Vocoder*(*)()>(dlsym(library,"create"));
 auto destroy=reinterpret_cast<void(*)(Vocoder*)>(dlsym(library,"destroy"));
 if(!create||!destroy){dlclose(library);return nullptr;}
 auto encoder=create();auto decoder=create();
 if(!encoder||!decoder){if(encoder)destroy(encoder);if(decoder)destroy(decoder);dlclose(library);return nullptr;}
 return new Codec{library,encoder,decoder,destroy};
}
extern "C" int allmode_codec_encode(void* handle,const int16_t* pcm,uint8_t* voice) {
 if(!handle||!pcm||!voice)return -1;
 int16_t input[160];uint8_t frame[72]={};std::memcpy(input,pcm,sizeof input);
 static_cast<Codec*>(handle)->encoder->encode_2400x1200(input,frame);
 std::memcpy(voice,frame,9);return 0;
}
extern "C" int allmode_codec_decode(void* handle,const uint8_t* voice,int16_t* pcm) {
 if(!handle||!pcm||!voice)return -1;
 uint8_t frame[72]={};std::memcpy(frame,voice,9);
 static_cast<Codec*>(handle)->decoder->decode_2400x1200(pcm,frame);return 0;
}
extern "C" void allmode_codec_close(void* handle) {
 if(!handle)return;auto codec=static_cast<Codec*>(handle);
 codec->destroy(codec->encoder);codec->destroy(codec->decoder);dlclose(codec->library);delete codec;
}
