// SPDX-License-Identifier: GPL-2.0
/*
 * XDP fast path for pre-armed QKD key material. On a hit, draw the key, turn
 * the packet around in place and XDP_TX it; on a miss, XDP_PASS to the KME.
 *
 * One lookup, no loop over the pre-arm set, so the instruction count is fixed
 * regardless of map occupancy. test/t1_insns.sh demonstrates that.
 */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include "prearm.h"

#define ETH_P_IP     0x0800
#define IPPROTO_UDP  17

/* Overridden at load time by the control plane (bpf_map__set_max_entries) so a
 * single object file can be loaded at any M_max. */
struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, 4096);
	__type(key, struct pair_key);
	__type(value, struct prearm_val);
} prearm_map SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, struct prearm_stats);
} stats_map SEC(".maps");

static __always_inline struct prearm_stats *stats(void)
{
	__u32 k = 0;
	return bpf_map_lookup_elem(&stats_map, &k);
}

static __always_inline void swap_mac(struct ethhdr *eth)
{
	__u8 t[6];
	__builtin_memcpy(t, eth->h_source, 6);
	__builtin_memcpy(eth->h_source, eth->h_dest, 6);
	__builtin_memcpy(eth->h_dest, t, 6);
}

SEC("xdp")
int xdp_prearm(struct xdp_md *ctx)
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
	if (ip->protocol != IPPROTO_UDP)
		return XDP_PASS;
	if (ip->ihl != 5)                       /* no options: keeps the swap exact */
		return XDP_PASS;

	struct udphdr *udp = (void *)(ip + 1);
	if ((void *)(udp + 1) > data_end)
		return XDP_PASS;
	if (udp->dest != bpf_htons(CONSENSUS_PORT))
		return XDP_PASS;

	struct cons_hdr *ch = (void *)(udp + 1);
	if ((void *)(ch + 1) > data_end)
		return XDP_PASS;
	if (ch->flags & CONS_FLAG_RESPONSE)     /* never answer our own answer */
		return XDP_PASS;

	__u32 a = ch->src_vid, b = ch->dst_vid;
	struct pair_key pk = { .lo = a < b ? a : b, .hi = a < b ? b : a };

	/* The single lookup. Constant cost, whatever |S| is. */
	struct prearm_val *pv = bpf_map_lookup_elem(&prearm_map, &pk);
	struct prearm_stats *st = stats();

	if (!pv) {
		if (st)
			st->misses++;
		return XDP_PASS;                /* slow path: userspace asks the KME */
	}

	/* TTL rollback happens in the data plane, so a stale reservation cannot
	 * outlive its lease even if the control plane has stalled. */
	if (pv->expiry_ns && t0 > pv->expiry_ns) {
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

	/* Draw from the pre-positioned key. */
	pv->offset    += need >> 3;
	pv->bits_left -= need;

	/* Turn the request around in place. Swapping the MACs, addresses and ports
	 * leaves the IPv4 header checksum's one's-complement sum unchanged, so it
	 * needs no recomputation; the UDP checksum is zeroed, which IPv4 permits. */
	swap_mac(eth);
	__be32 tmp_ip = ip->saddr;
	ip->saddr = ip->daddr;
	ip->daddr = tmp_ip;
	__be16 tmp_pt = udp->source;
	udp->source = udp->dest;
	udp->dest = tmp_pt;
	udp->check = 0;

	ch->flags |= CONS_FLAG_RESPONSE | CONS_FLAG_FASTPATH;

	if (st) {
		st->hits++;
		st->fast_ns += bpf_ktime_get_ns() - t0;
	}
	return XDP_TX;
}

char _license[] SEC("license") = "GPL";
