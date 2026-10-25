// SPDX-License-Identifier: GPL-2.0
/*
 * Traffic generator and latency probe. Times key requests per validator pair.
 * Fast-path replies come back with CONS_FLAG_FASTPATH set, so the two
 * populations are split by mechanism rather than by a latency threshold.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <linux/types.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include "../bpf/prearm.h"

static __u64 now_ns(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (__u64)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b)
{
	__u64 x = *(const __u64 *)a, y = *(const __u64 *)b;
	return x < y ? -1 : x > y;
}

static void report(const char *tag, __u64 *v, int n, int total)
{
	if (!n) { printf("%-10s n=0\n", tag); return; }
	qsort(v, n, sizeof(*v), cmp_u64);
	double mean = 0;
	for (int i = 0; i < n; i++) mean += (double)v[i];
	mean /= n;
	printf("%-10s n=%-6d %5.1f%%  mean=%9.1f us  p50=%9.1f us  "
	       "p99=%9.1f us  min=%8.1f us\n",
	       tag, n, 100.0 * n / total, mean / 1000.0,
	       v[n / 2] / 1000.0, v[(int)(n * 0.99)] / 1000.0, v[0] / 1000.0);
}

int main(int argc, char **argv)
{
	const char *dst = "10.77.0.1";
	int nreq = 2000, nval = 16, bits = 256, timeout_ms = 200, warmup = 100;

	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--dst") && i + 1 < argc)          dst = argv[++i];
		else if (!strcmp(argv[i], "--requests") && i + 1 < argc) nreq = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--validators") && i + 1 < argc) nval = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--bits") && i + 1 < argc)     bits = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--timeout-ms") && i + 1 < argc) timeout_ms = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--warmup") && i + 1 < argc)   warmup = atoi(argv[++i]);
	}

	int s = socket(AF_INET, SOCK_DGRAM, 0);
	if (s < 0) { perror("socket"); return 1; }
	struct timeval tv = { .tv_sec = timeout_ms / 1000,
			      .tv_usec = (timeout_ms % 1000) * 1000 };
	setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

	struct sockaddr_in sa = { .sin_family = AF_INET,
				  .sin_port = htons(CONSENSUS_PORT) };
	if (inet_pton(AF_INET, dst, &sa.sin_addr) != 1) {
		fprintf(stderr, "bad dst %s\n", dst); return 1;
	}

	__u64 *fast = calloc(nreq, sizeof(__u64));
	__u64 *slow = calloc(nreq, sizeof(__u64));
	int nf = 0, ns = 0, lost = 0, done = 0;

	srand(1234);
	for (int i = 0; i < nreq + warmup; i++) {
		int a = rand() % nval, b = rand() % nval;
		if (a == b) b = (b + 1) % nval;

		struct cons_hdr h = {0};
		h.src_vid = a; h.dst_vid = b;
		h.view = i; h.bits_needed = bits; h.seq = i;
		h.t_send_ns = now_ns();

		__u64 t0 = now_ns();
		if (sendto(s, &h, sizeof(h), 0, (struct sockaddr *)&sa, sizeof(sa)) < 0)
			continue;

		char buf[512];
		struct cons_hdr r;
		ssize_t got = recv(s, buf, sizeof(buf), 0);
		__u64 dt = now_ns() - t0;

		if (i < warmup) continue;
		if (got < (ssize_t)sizeof(r)) { lost++; done++; continue; }
		memcpy(&r, buf, sizeof(r));
		done++;
		if (r.flags & CONS_FLAG_FASTPATH) fast[nf++] = dt;
		else                              slow[ns++] = dt;
	}

	printf("\n--- consensus key-request latency (%d requests, %d bits each) ---\n",
	       done, bits);
	report("fast(XDP)", fast, nf, done);
	report("slow(KME)", slow, ns, done);
	if (lost) printf("%-10s n=%-6d %5.1f%%\n", "timeout", lost, 100.0 * lost / done);
	if (nf && ns) {
		qsort(fast, nf, sizeof(__u64), cmp_u64);
		qsort(slow, ns, sizeof(__u64), cmp_u64);
		printf("\nspeedup at p50: %.1fx    at p99: %.1fx\n",
		       (double)slow[ns / 2] / fast[nf / 2],
		       (double)slow[(int)(ns * 0.99)] / fast[(int)(nf * 0.99)]);
	}
	free(fast); free(slow);
	close(s);
	return 0;
}
