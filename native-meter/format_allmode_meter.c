/* SPDX-License-Identifier: GPL-2.0-only
 * ALLMODE's dedicated write-only 8 kHz signed-linear meter format.
 * Uses the Asterisk public format module API, built against exact ASL headers.
 * Unlike SLN recording output, this bypasses stdio buffering. No ordinary
 * audio format is replaced, and no audio is written to regular files.
 */
#define AST_MODULE "format_allmode_meter"
#define AST_MODULE_SELF_SYM __internal_format_allmode_meter_self
#include "asterisk.h"
#include "asterisk/mod_format.h"
#include "asterisk/module.h"
#include "asterisk/format_cache.h"
#include "meter_fifo.h"

static int prepare(struct ast_filestream *s, const char *comment)
{
    (void)comment;
    int result = meter_fifo_prepare(fileno(s->f));
#ifdef ALLMODE_METER_SELFTEST
    if (result) fprintf(stderr,"meter prepare fd=%d failed: %s\n",fileno(s->f),strerror(errno));
#endif
    return result;
}
static int emit(struct ast_filestream *s, struct ast_frame *f)
{
    return meter_fifo_write(fileno(s->f), f->data.ptr, f->datalen);
}
static int reject_read(struct ast_filestream *s) { (void)s; return -1; }
static struct ast_frame *no_read(struct ast_filestream *s, int *next)
{ (void)s; (void)next; return NULL; }
static int no_seek(struct ast_filestream *s, off_t offset, int whence)
{ (void)s; (void)offset; (void)whence; return -1; }
static int no_trunc(struct ast_filestream *s) { (void)s; return -1; }
static off_t no_tell(struct ast_filestream *s) { (void)s; return -1; }

static struct ast_format_def meter = {
    .name = "allmode_meter", .exts = "ameter",
    .open = reject_read, .rewrite = prepare, .write = emit,
    .read = no_read, .seek = no_seek, .trunc = no_trunc, .tell = no_tell,
};
#ifdef ALLMODE_METER_SELFTEST
#include "module_selftest.h"
#endif
static int unload_module(void) {
#ifdef ALLMODE_METER_SELFTEST
    ast_cli_unregister(&test_cli);
#endif
    return ast_format_def_unregister(meter.name);
}
static int load_module(void)
{
    meter.format = ast_format_slin;
    if (ast_format_def_register(&meter)) return AST_MODULE_LOAD_DECLINE;
#ifdef ALLMODE_METER_SELFTEST
    ast_cli_register(&test_cli);
#endif
    return AST_MODULE_LOAD_SUCCESS;
}
AST_MODULE_INFO(ASTERISK_GPL_KEY, AST_MODFLAG_LOAD_ORDER,
    "ALLMODE unbuffered FIFO-only live meters",
    .support_level = AST_MODULE_SUPPORT_EXTENDED,
    .load = load_module, .unload = unload_module,
    .load_pri = AST_MODPRI_APP_DEPEND);
