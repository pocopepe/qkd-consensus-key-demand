// SPDX-License-Identifier: GPL-2.0
/*
 * Kernel-resident enforcement of predicted QKD key allocations.
 *
 * Beyond the minimal fast path this adds the three things a deployment needs and
 * a demo does not: sliding-window leases so an active pair is never evicted
 * mid-round, a per-validator token bucket so one pair cannot drain a shared
 * relay path, and amortised garbage collection so expired reservations are
 * reclaimed by the data plane instead of waiting on a userspace tick.
 *
 * The GC loop is the only loop, it is #pragma unroll'd to a compile-time
 * constant trip count, and its index is masked to the ring size, so the verifier
 * sees straight-line code with provably in-bounds accesses.
 */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include "maps.h"

#define ETH_P_IP     0x0800
#define IPPROTO_UDP  17
#define NS_PER_S     1000000000ULL

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, 4096);
	__type(key, struct pair_key);
	__type(value, struct prearm_val);
} prearm_map SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, MAX_VALIDATORS);
	__type(key, __u32);
	__type(value, struct qkd_token_bucket);
} token_map SEC(".maps");

/* Ring of recently installed keys, scanned a few slots per packet. */
struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, GC_RING_SIZE);
	__type(key, __u32);
	__type(value, struct pair_key);
} gc_ring SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, __u32);
} gc_cursor SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, struct enforcer_stats);
} stats_map SEC(".maps");

static __always_inline struct enforcer_stats *stats(void)
{
	__u32 k = 0;
	return bpf_map_lookup_elem(&stats_map, &k);
}

/* Amortised reclaim: scan a fixed number of ring slots and drop anything whose
 * hard lifetime has run out. Bounded trip count, masked index. */
static __always_inline int gc_sweep(__u64 now)
{
	__u32 ck = 0;
	__u32 *cur = bpf_map_lookup_elem(&gc_cursor, &ck);
	if (!cur)
		return 0;

	__u32 base = *cur;
	int reclaimed = 0;

#pragma unroll
	for (int i = 0; i < GC_SCAN_PER_PKT; i++) {
		__u32 idx = (base + i) & (GC_RING_SIZE - 1);
		struct pair_key *pk = bpf_map_lookup_elem(&gc_ring, &idx);
		if (!pk)
			continue;
		if (pk->lo == 0 && pk->hi == 0)
			continue;
		struct prearm_val *pv = bpf_map_lookup_elem(&prearm_map, pk);
		if (!pv) {
			struct pair_key zero = {};
			bpf_map_update_elem(&gc_ring, &idx, &zero, BPF_ANY);
			continue;
		}
		__u64 hard = pv->install_ns + pv->max_life_ns;
		if ((pv->max_life_ns && now > hard) ||
		    (pv->expiry_ns && now > pv->expiry_ns)) {
			/* Credit the owners before dropping the lease. A pair whose
			 * reservation expired unused is one the forecaster owes, and
			 * the daemon reads these credits to re-prioritise it rather
			 * than repeating the same miss next view. */
			__u32 a = pv->owner_a, b = pv->owner_b;
			if (a < MAX_VALIDATORS) {
				struct qkd_token_bucket *tb = bpf_map_lookup_elem(&token_map, &a);
				if (tb)
					tb->starved_credits++;
			}
			if (b < MAX_VALIDATORS) {
				struct qkd_token_bucket *tb = bpf_map_lookup_elem(&token_map, &b);
				if (tb)
					tb->starved_credits++;
			}
			bpf_map_delete_elem(&prearm_map, pk);
			struct pair_key zero = {};
			bpf_map_update_elem(&gc_ring, &idx, &zero, BPF_ANY);
			reclaimed++;
		}
	}
	__u32 next = (base + GC_SCAN_PER_PKT) & (GC_RING_SIZE - 1);
	bpf_map_update_elem(&gc_cursor, &ck, &next, BPF_ANY);
	return reclaimed;
}

/* Token bucket with lazy refill. Returns 1 if the draw is allowed. */
static __always_inline int take_tokens(__u32 vid, __u32 bits, __u64 now)
{
	if (vid >= MAX_VALIDATORS)
		return 1;
	struct qkd_token_bucket *tb = bpf_map_lookup_elem(&token_map, &vid);
	if (!tb || tb->capacity == 0)
		return 1;                       /* unconfigured: do not police */

	if (tb->last_refill_ns && now > tb->last_refill_ns) {
		__u64 dt = now - tb->last_refill_ns;
		/* dt is bounded to one second of refill to keep the arithmetic
		 * small and the verifier's range tracking happy */
		if (dt > NS_PER_S)
			dt = NS_PER_S;
		__u64 add = (tb->refill_bits_per_s * dt) / NS_PER_S;
		__u64 t = tb->tokens + add;
		tb->tokens = t > tb->capacity ? tb->capacity : t;
	}
	tb->last_refill_ns = now;

	if (tb->tokens < (__u64)bits) {
		tb->throttled++;
		return 0;
	}
	tb->tokens -= bits;
	return 1;
}

static __always_inline void swap_mac(struct ethhdr *eth)
{
	__u8 t[6];
	__builtin_memcpy(t, eth->h_source, 6);
	__builtin_memcpy(eth->h_source, eth->h_dest, 6);
	__builtin_memcpy(eth->h_dest, t, 6);
}

SEC("xdp")
int xdp_enforcer(struct xdp_md *ctx)
{
	void *data     = (void *)(long)ctx->data;
	void *data_end = (void *)(long)ctx->data_end;
	__u64 t0 = bpf_ktime_get_ns();

	struct ethhdr *eth = data;
	if ((void *)(eth + 1) > data_end)
		return XDP_PASS;
	if (eth->h_proto != bpf_htons(ETH_P_IP))
		return XDP_PASS;

	struct iphdr *ip = (void *)(eth + 1);
	if ((void *)(ip + 1) > data_end)
		return XDP_PASS;
	if (ip->protocol != IPPROTO_UDP || ip->ihl != 5)
		return XDP_PASS;

	struct udphdr *udp = (void *)(ip + 1);
	if ((void *)(udp + 1) > data_end)
		return XDP_PASS;
	if (udp->dest != bpf_htons(CONSENSUS_PORT))
		return XDP_PASS;

	struct cons_hdr *ch = (void *)(udp + 1);
	if ((void *)(ch + 1) > data_end)
		return XDP_PASS;
	if (ch->flags & CONS_FLAG_RESPONSE)
		return XDP_PASS;

	struct enforcer_stats *st = stats();

	int rec = gc_sweep(t0);
	if (st && rec)
		st->gc_reclaimed += rec;

	__u32 a = ch->src_vid, b = ch->dst_vid;
	struct pair_key pk = { .lo = a < b ? a : b, .hi = a < b ? b : a };

	struct prearm_val *pv = bpf_map_lookup_elem(&prearm_map, &pk);
	if (!pv) {
		if (st)
			st->misses++;
		return XDP_PASS;
	}

	__u64 hard = pv->install_ns + pv->max_life_ns;
	if ((pv->expiry_ns && t0 > pv->expiry_ns) ||
	    (pv->max_life_ns && t0 > hard)) {
		bpf_map_delete_elem(&prearm_map, &pk);
		if (st)
			st->expired++;
		return XDP_PASS;
	}

	__u32 need = ch->bits_needed;
	if (need > 65535 || pv->bits_left < need) {
		if (st)
			st->short_key++;
		return XDP_PASS;
	}

	/* Policing happens before the draw, so a throttled request leaves the
	 * reservation untouched for the pairs that have not exceeded their share. */
	if (!take_tokens(a, need, t0)) {
		if (st)
			st->throttled++;
		ch->flags |= CONS_FLAG_THROTTLED;
		return XDP_PASS;
	}

	pv->offset    += need >> 3;
	pv->bits_left -= need;
	pv->uses++;

	/* Slide the window forward, but never past the hard ceiling. */
	if (pv->lease_ns) {
		__u64 want = t0 + pv->lease_ns;
		if (pv->max_life_ns && want > hard)
			want = hard;
		if (want > pv->expiry_ns) {
			pv->expiry_ns = want;
			if (st)
				st->renewals++;
		}
	}

	swap_mac(eth);
	__be32 tip = ip->saddr;
	ip->saddr = ip->daddr;
	ip->daddr = tip;
	__be16 tpt = udp->source;
	udp->source = udp->dest;
	udp->dest = tpt;
	udp->check = 0;
	ch->flags |= CONS_FLAG_RESPONSE | CONS_FLAG_FASTPATH;

	if (st) {
		st->hits++;
		st->fast_ns += bpf_ktime_get_ns() - t0;
	}
	return XDP_TX;
}

char _license[] SEC("license") = "GPL";
