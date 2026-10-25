// SPDX-License-Identifier: GPL-2.0
/*
 * Userspace control plane: loads and attaches the XDP program, then applies
 * pre-arm plans read from stdin. Kept thin so the syscall cost of a commit is
 * measurable on its own -- that cost is what bounds U_max.
 *
 * Commands (one per line on stdin):
 *   ARM  <lo> <hi> <bits> <ttl_ms>   stage an insert/update
 *   DEL  <lo> <hi>                   stage a delete
 *   COMMIT                           apply staged ops, report syscalls + wall ns
 *   COMMIT BATCH                     same, via BPF_MAP_UPDATE_BATCH
 *   STATS                            print aggregated per-CPU counters
 *   CLEAR                            drop every entry
 *   COUNT                            number of live entries
 *   QUIT
 */
#define _GNU_SOURCE
#include <linux/if_link.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <net/if.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "prearm.h"

#define MAX_STAGED 65536

static volatile sig_atomic_t stop;
static int ifindex;

static void on_sig(int s) { (void)s; stop = 1; }

static __u64 now_ns(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (__u64)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

struct staged {
	struct pair_key k;
	struct prearm_val v;
	int del;
};

static struct staged staged[MAX_STAGED];
static int n_staged;

static int do_commit(int mapfd, int use_batch)
{
	__u64 t0 = now_ns();
	int syscalls = 0, errs = 0;

	if (use_batch) {
		static struct pair_key keys[MAX_STAGED];
		static struct prearm_val vals[MAX_STAGED];
		static struct pair_key dkeys[MAX_STAGED];
		__u32 nu = 0, nd = 0;

		for (int i = 0; i < n_staged; i++) {
			if (staged[i].del) {
				dkeys[nd++] = staged[i].k;
			} else {
				keys[nu] = staged[i].k;
				vals[nu] = staged[i].v;
				nu++;
			}
		}
		if (nd) {
			__u32 cnt = nd;
			if (bpf_map_delete_batch(mapfd, dkeys, &cnt, NULL) && errno != ENOENT)
				errs++;
			syscalls++;
		}
		if (nu) {
			__u32 cnt = nu;
			if (bpf_map_update_batch(mapfd, keys, vals, &cnt, NULL))
				errs++;
			syscalls++;
		}
	} else {
		for (int i = 0; i < n_staged; i++) {
			int r;
			if (staged[i].del)
				r = bpf_map_delete_elem(mapfd, &staged[i].k);
			else
				r = bpf_map_update_elem(mapfd, &staged[i].k,
							&staged[i].v, BPF_ANY);
			syscalls++;
			if (r && !(staged[i].del && errno == ENOENT))
				errs++;
		}
	}
	__u64 dt = now_ns() - t0;
	printf("COMMITTED ops=%d syscalls=%d errors=%d wall_ns=%llu ns_per_op=%.1f\n",
	       n_staged, syscalls, errs, (unsigned long long)dt,
	       n_staged ? (double)dt / n_staged : 0.0);
	fflush(stdout);
	n_staged = 0;
	return errs;
}

static void do_stats(int fd)
{
	int ncpu = libbpf_num_possible_cpus();
	struct prearm_stats *per = calloc(ncpu, sizeof(*per));
	struct prearm_stats agg = {0};
	__u32 k = 0;

	if (per && !bpf_map_lookup_elem(fd, &k, per)) {
		for (int i = 0; i < ncpu; i++) {
			agg.hits      += per[i].hits;
			agg.misses    += per[i].misses;
			agg.expired   += per[i].expired;
			agg.short_key += per[i].short_key;
			agg.fast_ns   += per[i].fast_ns;
		}
	}
	printf("STATS hits=%llu misses=%llu expired=%llu short_key=%llu "
	       "fast_ns_total=%llu fast_ns_per_hit=%.1f\n",
	       (unsigned long long)agg.hits, (unsigned long long)agg.misses,
	       (unsigned long long)agg.expired, (unsigned long long)agg.short_key,
	       (unsigned long long)agg.fast_ns,
	       agg.hits ? (double)agg.fast_ns / agg.hits : 0.0);
	fflush(stdout);
	free(per);
}

static void do_clear(int fd)
{
	struct pair_key k, next;
	int n = 0;
	memset(&k, 0, sizeof(k));
	while (!bpf_map_get_next_key(fd, n ? &k : NULL, &next)) {
		bpf_map_delete_elem(fd, &next);
		k = next;
		n++;
		if (n > 1000000) break;
	}
	printf("CLEARED %d\n", n);
	fflush(stdout);
}

static int do_count(int fd)
{
	struct pair_key k, next;
	int n = 0, first = 1;
	while (!bpf_map_get_next_key(fd, first ? NULL : &k, &next)) {
		k = next; first = 0; n++;
		if (n > 1000000) break;
	}
	return n;
}

static void usage(const char *p)
{
	fprintf(stderr,
		"usage: %s --iface IF [--max-entries N] [--mode native|skb]\n"
		"       %s --insns-only [--max-entries N]\n", p, p);
}

int main(int argc, char **argv)
{
	const char *iface = NULL;
	int max_entries = 4096, insns_only = 0;
	__u32 xdp_flags = XDP_FLAGS_DRV_MODE;

	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--iface") && i + 1 < argc)      iface = argv[++i];
		else if (!strcmp(argv[i], "--max-entries") && i + 1 < argc)
			max_entries = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--insns-only"))            insns_only = 1;
		else if (!strcmp(argv[i], "--mode") && i + 1 < argc)
			xdp_flags = strcmp(argv[++i], "skb") ? XDP_FLAGS_DRV_MODE
							     : XDP_FLAGS_SKB_MODE;
		else { usage(argv[0]); return 2; }
	}
	if (!iface && !insns_only) { usage(argv[0]); return 2; }

	struct bpf_object *obj = bpf_object__open_file("bpf/prearm.bpf.o", NULL);
	if (!obj) { fprintf(stderr, "open failed: %s\n", strerror(errno)); return 1; }

	struct bpf_map *pm = bpf_object__find_map_by_name(obj, "prearm_map");
	struct bpf_program *prog = bpf_object__find_program_by_name(obj, "xdp_prearm");
	if (!pm || !prog) { fprintf(stderr, "map/prog not found\n"); return 1; }

	/* M_max is a load-time property of the map, not of the program. */
	if (bpf_map__set_max_entries(pm, max_entries)) {
		fprintf(stderr, "set_max_entries failed\n"); return 1;
	}

	if (bpf_object__load(obj)) {
		fprintf(stderr, "load failed: %s\n", strerror(errno));
		return 1;
	}

	/* The number the whole instruction-budget argument turns on. */
	struct bpf_prog_info info = {};
	__u32 ilen = sizeof(info);
	int pfd = bpf_program__fd(prog);
	if (!bpf_obj_get_info_by_fd(pfd, &info, &ilen)) {
		printf("PROG name=%s verified_insns=%u xlated_bytes=%u jited_bytes=%u "
		       "map_max_entries=%d\n",
		       info.name, info.verified_insns, info.xlated_prog_len,
		       info.jited_prog_len, max_entries);
		fflush(stdout);
	}
	if (insns_only) { bpf_object__close(obj); return 0; }

	ifindex = if_nametoindex(iface);
	if (!ifindex) { fprintf(stderr, "no iface %s\n", iface); return 1; }

	if (bpf_xdp_attach(ifindex, pfd, xdp_flags, NULL)) {
		fprintf(stderr, "attach (drv) failed: %s; retrying skb mode\n",
			strerror(errno));
		xdp_flags = XDP_FLAGS_SKB_MODE;
		if (bpf_xdp_attach(ifindex, pfd, xdp_flags, NULL)) {
			fprintf(stderr, "attach failed: %s\n", strerror(errno));
			return 1;
		}
	}
	printf("ATTACHED iface=%s ifindex=%d mode=%s max_entries=%d\n",
	       iface, ifindex,
	       xdp_flags == XDP_FLAGS_DRV_MODE ? "native" : "skb", max_entries);
	fflush(stdout);

	signal(SIGINT, on_sig);
	signal(SIGTERM, on_sig);

	int mapfd = bpf_map__fd(pm);
	int statfd = bpf_map__fd(bpf_object__find_map_by_name(obj, "stats_map"));

	char line[256];
	while (!stop && fgets(line, sizeof(line), stdin)) {
		unsigned lo, hi, bits, ttl;
		if (sscanf(line, "ARM %u %u %u %u", &lo, &hi, &bits, &ttl) == 4) {
			if (n_staged >= MAX_STAGED) continue;
			struct staged *s = &staged[n_staged++];
			memset(s, 0, sizeof(*s));
			s->k.lo = lo < hi ? lo : hi;
			s->k.hi = lo < hi ? hi : lo;
			s->v.bits_left = bits;
			s->v.expiry_ns = ttl ? now_ns() + (__u64)ttl * 1000000ull : 0;
			for (int i = 0; i < KEY_ID_BYTES; i++)
				s->v.key_id[i] = (__u8)(lo * 31 + hi * 17 + i);
		} else if (sscanf(line, "DEL %u %u", &lo, &hi) == 2) {
			if (n_staged >= MAX_STAGED) continue;
			struct staged *s = &staged[n_staged++];
			memset(s, 0, sizeof(*s));
			s->k.lo = lo < hi ? lo : hi;
			s->k.hi = lo < hi ? hi : lo;
			s->del = 1;
		} else if (!strncmp(line, "COMMIT BATCH", 12)) {
			do_commit(mapfd, 1);
		} else if (!strncmp(line, "COMMIT", 6)) {
			do_commit(mapfd, 0);
		} else if (!strncmp(line, "STATS", 5)) {
			do_stats(statfd);
		} else if (!strncmp(line, "CLEAR", 5)) {
			do_clear(mapfd);
		} else if (!strncmp(line, "COUNT", 5)) {
			printf("COUNT %d\n", do_count(mapfd)); fflush(stdout);
		} else if (!strncmp(line, "QUIT", 4)) {
			break;
		}
	}

	bpf_xdp_detach(ifindex, xdp_flags, NULL);
	bpf_object__close(obj);
	printf("DETACHED\n");
	return 0;
}
