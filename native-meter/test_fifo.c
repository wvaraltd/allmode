/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include "meter_fifo.h"
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec/1e9; }
int main(void)
{
    int p[2]; unsigned char frame[320], out[320];
    memset(frame, 0x13, sizeof(frame));
    assert(pipe(p)==0); assert(meter_fifo_prepare(p[1])==0);
    assert(fcntl(p[0],F_SETFL,O_NONBLOCK)==0);
    double worst=0;
    for(int i=0;i<500;i++) {
        double t=now();
        assert(meter_fifo_write(p[1],frame,sizeof(frame))==0);
        assert(read(p[0],out,sizeof(out))==sizeof(out));
        assert(memcmp(frame,out,sizeof(out))==0);
        double elapsed=now()-t; if(elapsed>worst)worst=elapsed;
    }
    assert(meter_fifo_write(p[1],frame,1)==-1);
    assert(meter_fifo_write(p[1],frame,PIPE_BUF+2)==-1);
    assert(meter_fifo_write(p[1],NULL,320)==-1);
    assert(meter_fifo_write(p[1],NULL,0)==0);
    int count=0; double t=now();
    while(meter_fifo_write(p[1],frame,sizeof(frame))==0)assert(++count<10000);
    assert(errno==EAGAIN || errno==EWOULDBLOCK);
    assert(now()-t<1.0);
    close(p[0]); signal(SIGPIPE,SIG_IGN);
    assert(meter_fifo_write(p[1],frame,sizeof(frame))==-1); assert(errno==EPIPE);
    close(p[1]);
    FILE *regular=tmpfile(); assert(regular);
    assert(meter_fifo_prepare(fileno(regular))==-1); fclose(regular);
    printf("PASS 500 immediate frame deliveries, worst write/read %.3f ms; malformed, full pipe, closed reader, regular-file rejection\n",worst*1000);
    return 0;
}
