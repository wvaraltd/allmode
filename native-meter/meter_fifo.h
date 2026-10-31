/* SPDX-License-Identifier: GPL-2.0-only
 * ALLMODE live-meter FIFO output. Never used for recordings or playback.
 */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/stat.h>
#include <unistd.h>

static int meter_fifo_prepare(int fd)
{
    struct stat st;
    int flags;
    if (fstat(fd, &st) || !S_ISFIFO(st.st_mode)) { errno = EINVAL; return -1; }
    flags = fcntl(fd, F_GETFL);
    if (flags == -1) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static int meter_fifo_write(int fd, const void *data, size_t size)
{
    ssize_t result;
    /* Atomic writes: never wait for a slow or disconnected meter reader.
     * Frames larger than PIPE_BUF cannot be emitted atomically, so reject.
     */
    if (!size) return 0;
    if (!data || size % 2 || size > PIPE_BUF) { errno = EINVAL; return -1; }
    do { result = write(fd, data, size); } while (result < 0 && errno == EINTR);
    return result == (ssize_t)size ? 0 : -1;
}
