#include <errno.h>
#include <seccomp.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv) {
    (void)argc;
    scmp_filter_ctx filter = seccomp_init(SCMP_ACT_ALLOW);
    if (!filter) return 125;
    // Inherited by every child, including Python and package managers.
    const char *blocked[] = {"socket", "connect", "io_uring_setup", "ptrace",
                            "process_vm_writev", "pidfd_getfd"};
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
    argv[0] = "/bin/bash";
    execv(argv[0], argv);
    perror("Cannot execute bash");
    return 125;
}
