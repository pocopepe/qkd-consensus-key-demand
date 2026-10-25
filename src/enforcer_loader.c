// SPDX-License-Identifier: GPL-2.0
/*
 * Loads xdp_enforcer.o, attaches it, and pins its maps under /sys/fs/bpf/qkd/.
 *
 * The process then exits: the XDP attachment lives on the netdev and the maps
 * live in bpffs, so the Python daemon can pick them up by path and drive them
 * with its own bpf() calls without this process staying in the loop.
 */
#include <linux/if_link.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <net/if.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define PIN_DIR "/sys/fs/bpf/qkd"

static const char *MAPS[] = { "prearm_map", "token_map", "gc_ring",
			      "gc_cursor", "stats_map" };

int main(int argc, char **argv)
{
	const char *iface = NULL;
	int max_entries = 4096, detach = 0;
	__u32 flags = XDP_FLAGS_DRV_MODE;

	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--iface") && i + 1 < argc) iface = argv[++i];
		else if (!strcmp(argv[i], "--max-entries") && i + 1 < argc)
			max_entries = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--mode") && i + 1 < argc)
			flags = strcmp(argv[++i], "skb") ? XDP_FLAGS_DRV_MODE
							: XDP_FLAGS_SKB_MODE;
		else if (!strcmp(argv[i], "--detach")) detach = 1;
		else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
	}
	if (!iface) { fprintf(stderr, "--iface required\n"); return 2; }

	int ifindex = if_nametoindex(iface);
	if (!ifindex) { fprintf(stderr, "no iface %s\n", iface); return 1; }

	if (detach) {
		bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, NULL);
		bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
		for (unsigned i = 0; i < sizeof(MAPS) / sizeof(*MAPS); i++) {
			char p[256];
			snprintf(p, sizeof(p), PIN_DIR "/%s", MAPS[i]);
			unlink(p);
		}
		rmdir(PIN_DIR);
		printf("DETACHED %s\n", iface);
		return 0;
	}

	mkdir(PIN_DIR, 0700);

	struct bpf_object *obj = bpf_object__open_file("src/xdp_enforcer.o", NULL);
	if (!obj) { fprintf(stderr, "open: %s\n", strerror(errno)); return 1; }

	struct bpf_map *pm = bpf_object__find_map_by_name(obj, "prearm_map");
	if (pm && bpf_map__set_max_entries(pm, max_entries)) {
		fprintf(stderr, "set_max_entries failed\n"); return 1;
	}
	if (bpf_object__load(obj)) {
		fprintf(stderr, "load: %s\n", strerror(errno)); return 1;
	}

	struct bpf_program *prog = bpf_object__find_program_by_name(obj, "xdp_enforcer");
	int pfd = bpf_program__fd(prog);

	struct bpf_prog_info info = {};
	__u32 ilen = sizeof(info);
	if (!bpf_obj_get_info_by_fd(pfd, &info, &ilen))
		printf("PROG verified_insns=%u xlated_bytes=%u jited_bytes=%u "
		       "max_entries=%d\n", info.verified_insns,
		       info.xlated_prog_len, info.jited_prog_len, max_entries);

	for (unsigned i = 0; i < sizeof(MAPS) / sizeof(*MAPS); i++) {
		struct bpf_map *m = bpf_object__find_map_by_name(obj, MAPS[i]);
		char p[256];
		snprintf(p, sizeof(p), PIN_DIR "/%s", MAPS[i]);
		unlink(p);
		if (!m || bpf_map__pin(m, p)) {
			fprintf(stderr, "pin %s failed: %s\n", MAPS[i], strerror(errno));
			return 1;
		}
	}

	if (bpf_xdp_attach(ifindex, pfd, flags, NULL)) {
		flags = XDP_FLAGS_SKB_MODE;
		if (bpf_xdp_attach(ifindex, pfd, flags, NULL)) {
			fprintf(stderr, "attach: %s\n", strerror(errno)); return 1;
		}
	}
	printf("ATTACHED iface=%s mode=%s pinned=%s\n", iface,
	       flags == XDP_FLAGS_DRV_MODE ? "native" : "skb", PIN_DIR);
	bpf_object__close(obj);
	return 0;
}
