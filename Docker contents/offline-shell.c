#define _GNU_SOURCE
#include <errno.h>
#include <seccomp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

extern char **environ;

// Same name rule as redact.ts: credentials stay in Pi, never reach shell commands.
static int remove_secrets(void) {
    for (char **entry = environ; *entry;) {
        char *name = strndup(*entry, strcspn(*entry, "="));
        if (!name) return -1;
        int secret = strcasestr(name, "KEY") || strcasestr(name, "TOKEN") ||
                     strcasestr(name, "SECRET");
        int failed = secret && unsetenv(name) != 0;
        free(name);
        if (failed) return -1;
        entry = secret ? environ : entry + 1;  // unsetenv shifts environ
    }
    return 0;
}

int main(int argc, char **argv) {
    (void)argc;
    scmp_filter_ctx filter = seccomp_init(SCMP_ACT_ALLOW);
    if (!filter) return 125;
    // Inherited by every child, including Python and package managers.
    // Local Unix sockets stay available (Xvfb for cgx); every other family is refused,
    // so connect() can only reach Unix sockets and needs no rule of its own.
    if (seccomp_rule_add(filter, SCMP_ACT_ERRNO(EPERM), SCMP_SYS(socket), 1,
                         SCMP_A0(SCMP_CMP_NE, AF_UNIX)) < 0) {
        seccomp_release(filter);
        return 125;
    }
    const char *blocked[] = {"io_uring_setup", "ptrace",
                            "process_vm_readv", "process_vm_writev", "pidfd_getfd"};
    for (unsigned i = 0; i < sizeof(blocked) / sizeof(blocked[0]); i++) {
        int syscall = seccomp_syscall_resolve_name(blocked[i]);
        if (syscall == __NR_SCMP_ERROR ||
            seccomp_rule_add(filter, SCMP_ACT_ERRNO(EPERM), syscall, 0) < 0) {
            seccomp_release(filter);
            return 125;
        }
    }
    if (seccomp_load(filter) < 0) {
        perror("Cannot enforce offline shell");
        seccomp_release(filter);
        return 125;
    }
    seccomp_release(filter);
    if (remove_secrets() != 0) {
        perror("Cannot remove API credentials");
        return 125;
    }
    argv[0] = "/bin/bash";
    execv(argv[0], argv);
    perror("Cannot execute bash");
    return 125;
}
