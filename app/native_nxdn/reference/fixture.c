/* Derived fixture: Copyright (C) 2019-2021 Doug McLain.
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
static unsigned m_txcnt;
static uint16_t m_nxdnid=1234;
static struct { uint16_t gwid; } m_modeinfo={5678};
static bool m_eot=false, m_hwtx=false;
static uint8_t m_nxdnframe[55],m_lich,m_sacch[5],m_layer3[22],m_ambe[36];
const int dvsi_interleave[49] = {
	0, 3, 6,  9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 41, 43, 45, 47,
	1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 42, 44, 46, 48,
	2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38
};

const uint8_t NXDN_LICH_RFCT_RDCH			= 2U;
const uint8_t NXDN_LICH_USC_SACCH_NS		= 0U;
const uint8_t NXDN_LICH_USC_SACCH_SS		= 2U;
const uint8_t NXDN_LICH_STEAL_FACCH			= 0U;
const uint8_t NXDN_LICH_STEAL_NONE			= 3U;
const uint8_t NXDN_LICH_DIRECTION_INBOUND	= 0U;
const uint8_t NXDN_MESSAGE_TYPE_VCALL       = 1U;
const uint8_t NXDN_MESSAGE_TYPE_TX_REL      = 8U;

const uint8_t BIT_MASK_TABLE[] = { 0x80U, 0x40U, 0x20U, 0x10U, 0x08U, 0x04U, 0x02U, 0x01U };
#define WRITE_BIT1(p,i,b) p[(i)>>3] = (b) ? (p[(i)>>3] | BIT_MASK_TABLE[(i)&7]) : (p[(i)>>3] & ~BIT_MASK_TABLE[(i)&7])
#define READ_BIT1(p,i)    (p[(i)>>3] & BIT_MASK_TABLE[(i)&7])


uint8_t * get_frame();
void encode_header();
void encode_data();
void deinterleave_ambe(uint8_t *d);
uint8_t get_lich_fct(uint8_t lich);
void set_lich_rfct(uint8_t rfct);
void set_lich_fct(uint8_t fct);
void set_lich_option(uint8_t o);
void set_lich_dir(uint8_t d);
uint8_t get_lich();
void set_sacch_ran(uint8_t ran);
void set_sacch_struct(uint8_t s);
void set_sacch_data(const uint8_t *d);
void get_sacch(uint8_t *d);
void set_layer3_msgtype(uint8_t t);
void set_layer3_srcid(uint16_t src);
void set_layer3_dstid(uint16_t dst);
void set_layer3_grp(bool grp);
void set_layer3_blks(uint8_t b);
void layer3_encode(uint8_t* d, uint8_t len, uint8_t offset);
void encode_crc6(uint8_t *d, uint8_t len);
uint8_t * get_frame()
{
	memcpy(m_nxdnframe, "NXDND", 5);
	m_nxdnframe[5U] = (m_nxdnid >> 8) & 0xFFU;
	m_nxdnframe[6U] = (m_nxdnid >> 0) & 0xFFU;
	m_nxdnframe[7U] = (m_modeinfo.gwid >> 8) & 0xFFU;
	m_nxdnframe[8U] = (m_modeinfo.gwid >> 0) & 0xFFU;
	m_nxdnframe[9U] = 0x01U;

	if(!m_txcnt || m_eot){
		encode_header();
	}
	else{
		encode_data();
	}
	if (m_nxdnframe[10U] == 0x81U || m_nxdnframe[10U] == 0x83U) {
		m_nxdnframe[9U] |= m_nxdnframe[15U] == 0x01U ? 0x04U : 0x00U;
		m_nxdnframe[9U] |= m_nxdnframe[15U] == 0x08U ? 0x08U : 0x00U;
	}
	else if ((m_nxdnframe[10U] & 0xF0U) == 0x90U) {
		m_nxdnframe[9U] |= 0x02U;
		if (m_nxdnframe[10U] == 0x90U || m_nxdnframe[10U] == 0x92U || m_nxdnframe[10U] == 0x9CU || m_nxdnframe[10U] == 0x9EU) {
			m_nxdnframe[9U] |= m_nxdnframe[12U] == 0x09U ? 0x04U : 0x00U;
			m_nxdnframe[9U] |= m_nxdnframe[12U] == 0x08U ? 0x08U : 0x00U;
		}
	}
	if(m_eot){
		m_txcnt = 0;
		m_eot = false;
	}
	else{
		++m_txcnt;
	}
	return m_nxdnframe;
}

void encode_header()
{
	const uint8_t idle[3U] = {0x10, 0x00, 0x00};
	m_lich = 0;
	memset(m_sacch, 0, 5U);
	memset(m_layer3, 0, 22U);
	set_lich_rfct(NXDN_LICH_RFCT_RDCH);
	set_lich_fct(NXDN_LICH_USC_SACCH_NS);
	set_lich_option(NXDN_LICH_STEAL_FACCH);
	set_lich_dir(NXDN_LICH_DIRECTION_INBOUND);
	m_nxdnframe[10U] = get_lich();

	set_sacch_ran(0x01);
	set_sacch_struct(0); //Single
	set_sacch_data(idle);
	get_sacch(&m_nxdnframe[11U]);
	if(m_eot){
		set_layer3_msgtype(NXDN_MESSAGE_TYPE_TX_REL);
	}
	else{
		set_layer3_msgtype(NXDN_MESSAGE_TYPE_VCALL);
	}
	set_layer3_srcid(m_nxdnid);
	set_layer3_dstid(m_modeinfo.gwid);
	set_layer3_grp(true);
	set_layer3_blks(0U);
	memcpy(&m_nxdnframe[15U], m_layer3, 14U);
	memcpy(&m_nxdnframe[29U], m_layer3, 14U);
}

void encode_data()
{
	uint8_t msg[3U];
	m_lich = 0;
	memset(m_sacch, 0, 5U);
	memset(m_layer3, 0, 22U);
	set_lich_rfct(NXDN_LICH_RFCT_RDCH);
	set_lich_fct(NXDN_LICH_USC_SACCH_SS);
	set_lich_option(NXDN_LICH_STEAL_NONE);
	set_lich_dir(NXDN_LICH_DIRECTION_INBOUND);
	m_nxdnframe[10U] = get_lich();

	set_sacch_ran(0x01);

	set_layer3_msgtype(NXDN_MESSAGE_TYPE_VCALL);
	set_layer3_srcid(m_nxdnid);
	set_layer3_dstid(m_modeinfo.gwid);
	set_layer3_grp(true);
	set_layer3_blks(0U);

	switch(m_txcnt % 4){
	case 0:
		set_sacch_struct(3);
		layer3_encode(msg, 18U, 0U);
		set_sacch_data(msg);
		break;
	case 1:
		set_sacch_struct(2);
		layer3_encode(msg, 18U, 18U);
		set_sacch_data(msg);
		break;
	case 2:
		set_sacch_struct(1);
		layer3_encode(msg, 18U, 36U);
		set_sacch_data(msg);
		break;
	case 3:
		set_sacch_struct(0);
		layer3_encode(msg, 18U, 54U);
		set_sacch_data(msg);
		break;
	}
	get_sacch(&m_nxdnframe[11U]);

	if(m_hwtx){
		for(int i = 0; i < 4; ++i){
			deinterleave_ambe(&m_ambe[7*i]);
		}
	}

	memcpy(&m_nxdnframe[15], m_ambe, 7);
	for(int i = 0; i < 7; ++i){
		m_nxdnframe[21+i] |= (m_ambe[7+i] >> 1);
		m_nxdnframe[22+i] = (m_ambe[7+i] & 1) << 7;
	}
	m_nxdnframe[28] |= (m_ambe[13] >> 2);

	memcpy(&m_nxdnframe[29], &m_ambe[14], 7);
	for(int i = 0; i < 7; ++i){
		m_nxdnframe[35+i] |= (m_ambe[21+i] >> 1);
		m_nxdnframe[36+i] = (m_ambe[21+i] & 1) << 7;
	}
	m_nxdnframe[41] |= (m_ambe[27] >> 2);
}

void deinterleave_ambe(uint8_t *d)
{
	uint8_t dvsi_data[49];
	uint8_t ambe_data[7];
	memset(ambe_data, 0, 7);

	for(int i = 0; i < 6; ++i){
		for(int j = 0; j < 8; j++){
			dvsi_data[j+(8*i)] = (1 & (d[i] >> (7 - j)));
		}
	}
	dvsi_data[48] = (1 & (d[6] >> 7));

	for(int i = 0, j; i < 49; ++i){
		j = dvsi_interleave[i];
		ambe_data[i/8] += (dvsi_data[j])<<(7-(i%8));
		//j = dvsi_deinterleave[i];
		//ambe_data[j/8] += (dvsi_data[i])<<(7-(j%8));
	}
	memcpy(d, ambe_data, 7);
}

uint8_t get_lich_fct(uint8_t lich)
{
	return (lich >> 4) & 0x03U;
}

void set_lich_rfct(uint8_t rfct)
{
	m_lich &= 0x3FU;
	m_lich |= (rfct << 6) & 0xC0U;
}

void set_lich_fct(uint8_t fct)
{
	m_lich &= 0xCFU;
	m_lich |= (fct << 4) & 0x30U;
}

void set_lich_option(uint8_t o)
{
	m_lich &= 0xF3U;
	m_lich |= (o << 2) & 0x0CU;
}

void set_lich_dir(uint8_t d)
{
	m_lich &= 0xFDU;
	m_lich |= (d << 1) & 0x02U;
}

uint8_t get_lich()
{
	bool parity;
	switch (m_lich & 0xF0U) {
	case 0x80U:
	case 0xB0U:
		parity = true;
		break;
	default:
		parity = false;
	}
	if (parity)
		m_lich |= 0x01U;
	else
		m_lich &= 0xFEU;

	return m_lich;
}


void set_sacch_ran(uint8_t ran)
{
	m_sacch[0] &= 0xC0U;
	m_sacch[0] |= ran;
}

void set_sacch_struct(uint8_t s)
{
	m_sacch[0] &= 0x3FU;
	m_sacch[0] |= (s << 6) & 0xC0U;;
}

void set_sacch_data(const uint8_t *d)
{
	uint8_t offset = 8U;
	for (uint8_t i = 0U; i < 18U; i++, offset++) {
		bool b = READ_BIT1(d, i);
		WRITE_BIT1(m_sacch, offset, b);
	}
}

void get_sacch(uint8_t *d)
{
	memcpy(d, m_sacch, 4U);
	encode_crc6(d, 26);
}

void set_layer3_msgtype(uint8_t t)
{
	m_layer3[0] &= 0xC0U;
	m_layer3[0] |= t & 0x3FU;
}

void set_layer3_srcid(uint16_t src)
{
	m_layer3[3U] = (src >> 8) & 0xFF;
	m_layer3[4U] = (src >> 0) & 0xFF ;
}

void set_layer3_dstid(uint16_t dst)
{
	m_layer3[5U] = (dst >> 8) & 0xFF;
	m_layer3[6U] = (dst >> 0) & 0xFF ;
}

void set_layer3_grp(bool grp)
{
	m_layer3[2U] |= grp ? 0x20U : 0x20U;
}

void set_layer3_blks(uint8_t b)
{
	m_layer3[8U] &= 0xF0U;
	m_layer3[8U] |= b & 0x0FU;
}

void layer3_encode(uint8_t* d, uint8_t len, uint8_t offset)
{
	for (uint32_t i = 0U; i < len; i++, offset++) {
		bool b = READ_BIT1(m_layer3, offset);
		WRITE_BIT1(d, i, b);
	}
}

void encode_crc6(uint8_t *d, uint8_t len)
{
	uint8_t crc = 0x3FU;

	for (uint32_t i = 0U; i < len; i++) {
		bool bit1 = READ_BIT1(d, i) != 0x00U;
		bool bit2 = (crc & 0x20U) == 0x20U;
		crc <<= 1;

		if (bit1 ^ bit2)
			crc ^= 0x27U;
	}
	crc &= 0x3FU;
	uint8_t n = len;
	for (uint8_t i = 2U; i < 8U; i++, n++) {
		bool b = READ_BIT1((&crc), i);
		WRITE_BIT1(d, n, b);
	}
}


uint16_t createCRC12(const unsigned char* in, unsigned int length)
{
	uint16_t crc = 0x0FFFU;

	for (unsigned int i = 0U; i < length; i++) {
		bool bit1 = READ_BIT1(in, i) != 0x00U;
		bool bit2 = (crc & 0x0800U) == 0x0800U;

		crc <<= 1;

		if (bit1 ^ bit2)
			crc ^= 0x080FU;
	}

	return crc & 0x0FFFU;
}


static void dump(void){for(int i=0;i<43;i++)printf("%02x",m_nxdnframe[i]);puts("");}
int main(void){
 get_frame();dump();
 for(int i=0;i<4;i++){for(int j=0;j<6;j++)m_ambe[i*7+j]=i*7+j;m_ambe[i*7+6]=(i%2)?128:0;}
 get_frame();dump();m_eot=true;get_frame();dump();
 m_eot=false;m_txcnt=0;get_frame();
 uint16_t crc=createCRC12(m_nxdnframe+15,80);
 m_nxdnframe[25]=crc>>4;m_nxdnframe[26]=(crc&15)<<4;
 memcpy(m_nxdnframe+29,m_nxdnframe+15,14);dump();return 0;
}
