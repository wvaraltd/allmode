/* Derived reference: Copyright 2019-2021 Doug McLain, GPL-3.0-or-later. */
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "YSFFICH.h"
#include "YSFConvolution.h"
#include "CRCenc.h"
const unsigned YSF_SYNC_LENGTH_BYTES=5,YSF_FICH_LENGTH_BYTES=25,YSF_CALLSIGN_LENGTH=10;
static bool m_hwtx=false;
static uint8_t m_ambe[35],m_vch[13];
static const int dvsi_interleave[49]={0}; // Hardware branch never executed.
#define READ_BIT(p,i) ((p)[(i)/8]&(0x80>>((i)%8)))
#define WRITE_BIT(p,i,b) ((p)[(i)/8]=(b)?((p)[(i)/8]|(0x80>>((i)%8))):((p)[(i)/8]&~(0x80>>((i)%8))))
const uint32_t INTERLEAVE_TABLE_5_20[] = {
	0U, 40U,  80U, 120U, 160U,
	2U, 42U,  82U, 122U, 162U,
	4U, 44U,  84U, 124U, 164U,
	6U, 46U,  86U, 126U, 166U,
	8U, 48U,  88U, 128U, 168U,
	10U, 50U,  90U, 130U, 170U,
	12U, 52U,  92U, 132U, 172U,
	14U, 54U,  94U, 134U, 174U,
	16U, 56U,  96U, 136U, 176U,
	18U, 58U,  98U, 138U, 178U,
	20U, 60U, 100U, 140U, 180U,
	22U, 62U, 102U, 142U, 182U,
	24U, 64U, 104U, 144U, 184U,
	26U, 66U, 106U, 146U, 186U,
	28U, 68U, 108U, 148U, 188U,
	30U, 70U, 110U, 150U, 190U,
	32U, 72U, 112U, 152U, 192U,
	34U, 74U, 114U, 154U, 194U,
	36U, 76U, 116U, 156U, 196U,
	38U, 78U, 118U, 158U, 198U};

const uint32_t INTERLEAVE_TABLE_9_20[] = {
		0U, 40U,  80U, 120U, 160U, 200U, 240U, 280U, 320U,
		2U, 42U,  82U, 122U, 162U, 202U, 242U, 282U, 322U,
		4U, 44U,  84U, 124U, 164U, 204U, 244U, 284U, 324U,
		6U, 46U,  86U, 126U, 166U, 206U, 246U, 286U, 326U,
		8U, 48U,  88U, 128U, 168U, 208U, 248U, 288U, 328U,
	   10U, 50U,  90U, 130U, 170U, 210U, 250U, 290U, 330U,
	   12U, 52U,  92U, 132U, 172U, 212U, 252U, 292U, 332U,
	   14U, 54U,  94U, 134U, 174U, 214U, 254U, 294U, 334U,
	   16U, 56U,  96U, 136U, 176U, 216U, 256U, 296U, 336U,
	   18U, 58U,  98U, 138U, 178U, 218U, 258U, 298U, 338U,
	   20U, 60U, 100U, 140U, 180U, 220U, 260U, 300U, 340U,
	   22U, 62U, 102U, 142U, 182U, 222U, 262U, 302U, 342U,
	   24U, 64U, 104U, 144U, 184U, 224U, 264U, 304U, 344U,
	   26U, 66U, 106U, 146U, 186U, 226U, 266U, 306U, 346U,
	   28U, 68U, 108U, 148U, 188U, 228U, 268U, 308U, 348U,
	   30U, 70U, 110U, 150U, 190U, 230U, 270U, 310U, 350U,
	   32U, 72U, 112U, 152U, 192U, 232U, 272U, 312U, 352U,
	   34U, 74U, 114U, 154U, 194U, 234U, 274U, 314U, 354U,
	   36U, 76U, 116U, 156U, 196U, 236U, 276U, 316U, 356U,
	   38U, 78U, 118U, 158U, 198U, 238U, 278U, 318U, 358U};

const uint32_t INTERLEAVE_TABLE_26_4[] = {
	0U, 4U,  8U, 12U, 16U, 20U, 24U, 28U, 32U, 36U, 40U, 44U, 48U, 52U, 56U, 60U, 64U, 68U, 72U, 76U, 80U, 84U, 88U, 92U, 96U, 100U,
	1U, 5U,  9U, 13U, 17U, 21U, 25U, 29U, 33U, 37U, 41U, 45U, 49U, 53U, 57U, 61U, 65U, 69U, 73U, 77U, 81U, 85U, 89U, 93U, 97U, 101U,
	2U, 6U, 10U, 14U, 18U, 22U, 26U, 30U, 34U, 38U, 42U, 46U, 50U, 54U, 58U, 62U, 66U, 70U, 74U, 78U, 82U, 86U, 90U, 94U, 98U, 102U,
	3U, 7U, 11U, 15U, 19U, 23U, 27U, 31U, 35U, 39U, 43U, 47U, 51U, 55U, 59U, 63U, 67U, 71U, 75U, 79U, 83U, 87U, 91U, 95U, 99U, 103U};

const uint32_t WHITENING_DATA[] = {0x93U, 0xD7U, 0x51U, 0x21U, 0x9CU, 0x2FU, 0x6CU, 0xD0U, 0xEFU, 0x0FU,
										0xF8U, 0x3DU, 0xF1U, 0x73U, 0x20U, 0x94U, 0xEDU, 0x1EU, 0x7CU, 0xD8U};

const uint8_t BIT_MASK_TABLE[] = {0x80U, 0x40U, 0x20U, 0x10U, 0x08U, 0x04U, 0x02U, 0x01U};

#define WRITE_BIT(p,i,b) p[(i)>>3] = (b) ? (p[(i)>>3] | BIT_MASK_TABLE[(i)&7]) : (p[(i)>>3] & ~BIT_MASK_TABLE[(i)&7])
#define READ_BIT(p,i)    (p[(i)>>3] & BIT_MASK_TABLE[(i)&7])

void writeDataFRModeData1(const uint8_t* dt, uint8_t* data)
{
	data += YSF_SYNC_LENGTH_BYTES + YSF_FICH_LENGTH_BYTES;

	uint8_t output[25U];
	for (uint32_t i = 0U; i < 20U; i++)
		output[i] = dt[i] ^ WHITENING_DATA[i];

	CCRC::addCCITT162(output, 22U);
	output[22U] = 0x00U;

	uint8_t convolved[45U];

	CYSFConvolution conv;
	conv.encode(output, convolved, 180U);

	uint8_t bytes[45U];
	uint32_t j = 0U;
	for (uint32_t i = 0U; i < 180U; i++) {
		uint32_t n = INTERLEAVE_TABLE_9_20[i];

		bool s0 = READ_BIT(convolved, j) != 0U;
		j++;

		bool s1 = READ_BIT(convolved, j) != 0U;
		j++;

		WRITE_BIT(bytes, n, s0);

		n++;
		WRITE_BIT(bytes, n, s1);
	}

	uint8_t* p1 = data;
	uint8_t* p2 = bytes;
	for (uint32_t i = 0U; i < 5U; i++) {
		::memcpy(p1, p2, 9U);
		p1 += 18U; p2 += 9U;
	}
}

void writeDataFRModeData2(const uint8_t* dt, uint8_t* data)
{
	data += YSF_SYNC_LENGTH_BYTES + YSF_FICH_LENGTH_BYTES;

	uint8_t output[25U];
	for (uint32_t i = 0U; i < 20U; i++)
		output[i] = dt[i] ^ WHITENING_DATA[i];

	CCRC::addCCITT162(output, 22U);
	output[22U] = 0x00U;

	uint8_t convolved[45U];

	CYSFConvolution conv;
	conv.encode(output, convolved, 180U);

	uint8_t bytes[45U];
	uint32_t j = 0U;
	for (uint32_t i = 0U; i < 180U; i++) {
		uint32_t n = INTERLEAVE_TABLE_9_20[i];

		bool s0 = READ_BIT(convolved, j) != 0U;
		j++;

		bool s1 = READ_BIT(convolved, j) != 0U;
		j++;

		WRITE_BIT(bytes, n, s0);

		n++;
		WRITE_BIT(bytes, n, s1);
	}

	uint8_t* p1 = data + 9U;
	uint8_t* p2 = bytes;
	for (uint32_t i = 0U; i < 5U; i++) {
		::memcpy(p1, p2, 9U);
		p1 += 18U; p2 += 9U;
	}
}

void ysf_scramble(uint8_t *buf, const int len)
{	// buffer is (de)scrambled in place
	static const uint8_t scramble_code[180] = {
	1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1,
	0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1,
	1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1,
	0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0,
	1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1,
	1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 1,
	1, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1,
	0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0,
	1, 1, 1, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0,
	0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0
	};

	for (int i=0; i<len; i++) {
		buf[i] = buf[i] ^ scramble_code[i];
	}
}

void generate_vch_vd2(const uint8_t *a)
{
	uint8_t buf[104];
	uint8_t result[104];
	//uint8_t a[56];
	uint8_t vch[13];
	memset(vch, 0, 13);
/*
	for(int i = 0; i < 7; ++i){
		for(int j = 0; j < 8; ++j){
			a[(8*i)+j] = (1 & (input[i] >> (7-j)));
			//a[((8*i)+j)+1] = (1 & (data[5-i] >> j));
		}
	}
*/
	for (int i=0; i<27; i++) {
		buf[0+i*3] = a[i];
		buf[1+i*3] = a[i];
		buf[2+i*3] = a[i];
	}
	memcpy(buf+81, a+27, 22);
	buf[103] = 0;
	ysf_scramble(buf, 104);

	//uint8_t bit_result[104];
	int x=4;
	int y=26;
	for (int i=0; i<x; i++) {
		for (int j=0; j<y; j++) {
			result[i+j*x] = buf[j+i*y];
		}
	}
	for(int i = 0; i < 13; ++i){
		for(int j = 0; j < 8; ++j){
			//ambe_bytes[i] |= (ambe_frame[((8-i)*8)+(7-j)] << (7-j));
			vch[i] |= (result[(i*8)+j] << (7-j));
		}
	}
	::memcpy(m_vch, vch, 13);
}

void writeVDMode2Data(uint8_t* data, const uint8_t* dt)
{
	data += YSF_SYNC_LENGTH_BYTES + YSF_FICH_LENGTH_BYTES;
	
	uint8_t dt_tmp[13];
	::memcpy(dt_tmp, dt, YSF_CALLSIGN_LENGTH);

	for (uint32_t i = 0U; i < 10U; i++)
		dt_tmp[i] ^= WHITENING_DATA[i];

	CCRC::addCCITT162(dt_tmp, 12U);
	dt_tmp[12U] = 0x00U;

	uint8_t convolved[25U];
	CYSFConvolution conv;
	conv.start();
	conv.encode(dt_tmp, convolved, 100U);

	uint8_t bytes[25U];
	uint32_t j = 0U;
	for (uint32_t i = 0U; i < 100U; i++) {
		uint32_t n = INTERLEAVE_TABLE_5_20[i];

		bool s0 = READ_BIT(convolved, j) != 0U;
		j++;

		bool s1 = READ_BIT(convolved, j) != 0U;
		j++;

		WRITE_BIT(bytes, n, s0);

		n++;
		WRITE_BIT(bytes, n, s1);
	}

	uint8_t* p1 = data;
	uint8_t* p2 = bytes;
#ifdef SWDEBUG
	fprintf(stderr, "AMBE: ");
	for(int i = 0; i < 45; ++i){
		fprintf(stderr, "%02x ", m_ambe[i]);
	}
	fprintf(stderr, "\n");
	fflush(stderr);
#endif
	for (uint32_t i = 0U; i < 5U; i++) {
		::memcpy(p1, p2, 5U);
		if(m_hwtx){
			char ambe_bits[56];
			uint8_t di_bits[56];
			uint8_t *d = &m_ambe[7*i];
			for(int k = 0; k < 7; ++k){
				for(int j = 0; j < 8; j++){
					ambe_bits[j+(8*k)] = (1 & (d[k] >> (7 - j)));
					//ambe_bits[j+(8*ii)] = (1 & (d[ii] >> j));
				}
			}
			for(int k = 0; k < 49; ++k){
				di_bits[k] = ambe_bits[dvsi_interleave[k]];
			}
			generate_vch_vd2(di_bits);
		}
		else{
			uint8_t a[56];
			uint8_t *d = &m_ambe[7*i];
			for(int k = 0; k < 7; ++k){
				for(int j = 0; j < 8; ++j){
					a[(8*k)+j] = (1 & (d[k] >> (7-j)));
					//a[((8*i)+j)+1] = (1 & (data[5-i] >> j));
				}
			}
			generate_vch_vd2(a);
		}
		::memcpy(p1+5, m_vch, 13);
		p1 += 18U; p2 += 5U;
	}
}


static void dump(const uint8_t *b,int n){for(int i=0;i<n;i++)printf("%02x",b[i]);puts("");}
int main(){
 uint8_t frame[120]={0};CYSFFICH fich;
 fich.setFI(1);fich.setCS(2);fich.setFN(3);fich.setFT(6);fich.setDT(2);fich.setSQ(0);fich.encode(frame);dump(frame+5,25);
 writeDataFRModeData1((const uint8_t*)"**********N0CALL    ",frame);
 writeDataFRModeData2((const uint8_t*)"N0CALL    N0CALL    ",frame);dump(frame+30,90);
 for(int i=0;i<5;i++){for(int j=0;j<6;j++)m_ambe[i*7+j]=i*7+j;m_ambe[i*7+6]=(i%2)?128:0;}
 writeVDMode2Data(frame,(const uint8_t*)"N0CALL    ");dump(frame+30,90);
}
