CLANG   ?= clang-15
CC      ?= gcc
ARCH    := $(shell uname -m | sed 's/x86_64/x86/')

BPF_CFLAGS := -O2 -g -Wall -target bpf -D__TARGET_ARCH_$(ARCH) -I.
CTL_CFLAGS := -O2 -Wall -I.
CTL_LDLIBS := -lbpf -lelf -lz

all: prearm.bpf.o prearm_ctl

vmlinux.h:
	bpftool btf dump file /sys/kernel/btf/vmlinux format c > $@

prearm.bpf.o: prearm.bpf.c prearm.h vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

prearm_ctl: prearm_ctl.c prearm.h
	$(CC) $(CTL_CFLAGS) $< -o $@ $(CTL_LDLIBS)

clean:
	rm -f prearm.bpf.o prearm_ctl

.PHONY: all clean
