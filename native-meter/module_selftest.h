/* Synthetic test compiled ONLY into an isolated test module, never deployed. */
#include "asterisk/file.h"
#include "asterisk/cli.h"
#include <time.h>
static int module_selftest(void)
{
    char dir[]="/tmp/allmode-meter-selftest-XXXXXX",base[256],path[256];
    short pcm[160],got[160]; int r=-1, result=-1; struct ast_filestream *stream=NULL;
    struct timespec t0,t1; double worst=0;
    for(int i=0;i<160;i++)pcm[i]=(short)(i*31);
    if(!mkdtemp(dir))return -1;
    snprintf(base,sizeof(base),"%s/probe",dir);
    snprintf(path,sizeof(path),"%s/probe.ameter",dir);
    if(mkfifo(path,0600))goto done;
    r=open(path,O_RDONLY|O_NONBLOCK);if(r<0)goto done;
    stream=ast_writefile(base,"ameter",NULL,O_WRONLY,0,0600);if(!stream)goto done;
    struct ast_frame frame={.frametype=AST_FRAME_VOICE,.subclass.format=ast_format_slin,
                           .data.ptr=pcm,.datalen=sizeof(pcm),.samples=160};
    for(int i=0;i<500;i++){
        clock_gettime(CLOCK_MONOTONIC,&t0);
        if(ast_writestream(stream,&frame)||read(r,got,sizeof(got))!=sizeof(got)||memcmp(got,pcm,sizeof(got)))goto done;
        clock_gettime(CLOCK_MONOTONIC,&t1);
        double ms=(t1.tv_sec-t0.tv_sec)*1000.+(t1.tv_nsec-t0.tv_nsec)/1e6;
        if(ms>worst)worst=ms;
    }
    result=0;
    fprintf(stderr,"ALLMODE_SELFTEST_PASS: exact Asterisk ast_writefile/ast_writestream -> FIFO, 500 frames, worst %.3f ms\n",worst);
done:
    if(stream)ast_closestream(stream);
    if(r>=0)close(r);
    unlink(path);rmdir(dir);
    if(result)fprintf(stderr,"ALLMODE_SELFTEST_FAIL\n");
    return result;
}
static char *run_test_cli(struct ast_cli_entry *e, int cmd, struct ast_cli_args *a)
{
    if(cmd==CLI_INIT){e->command="allmode meter selftest";e->usage="Synthetic isolated test only\n";return NULL;}
    if(cmd==CLI_GENERATE)return NULL;
    if(a->argc!=3)return CLI_SHOWUSAGE;
    return module_selftest()?CLI_FAILURE:CLI_SUCCESS;
}
static struct ast_cli_entry test_cli=AST_CLI_DEFINE(run_test_cli,"Synthetic meter selftest");
