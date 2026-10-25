/* SPDX-License-Identifier: GPL-2.0
 *
 * Map layout shared by the XDP enforcer and the userspace daemon.
 */
#ifndef __QKD_MAPS_H
#define __QKD_MAPS_H

#define CONSENSUS_PORT   7788
#define KEY_ID_BYTES     16
#define MAX_VALIDATORS   1024
#define GC_RING_SIZE     1024          /* power of two: index masking */
#define GC_SCAN_PER_PKT  4             /* bounded loop trip count */

#define CONS_FLAG_RESPONSE 0x1
#define CONS_FLAG_FASTPATH 0x2
#define CONS_FLAG_THROTTLED 0x4

struct pair_key {
	__u32 lo;
	__u32 hi;
};

/* Pre-armed key with a sliding-window lease.
 *
 * install_ns pins the hard ceiling on how long a reservation may live;
 * expiry_ns slides forward on every use so an active pair is not evicted
 * mid-round, but a pair that goes silent falls out on its own. The two together
 * bound the damage from a wrong forecast without letting a right one be
 * cancelled by its own timer. */
struct prearm_val {
	__u8  key_id[KEY_ID_BYTES];
	__u32 offset;
	__u32 bits_left;
	__u64 install_ns;
	__u64 expiry_ns;
	__u64 lease_ns;        /* sliding window granted per use */
	__u64 max_life_ns;     /* hard ceiling measured from install_ns */
	__u32 uses;
	__u32 owner_a;         /* validators, kept for the starvation credit */
	__u32 owner_b;
	__u32 _pad;
};

/* Per-validator token bucket.
 *
 * Without this one pair can drain a shared relay path's pre-armed key and
 * starve every other pair routed over the same hops. The bucket caps how much
 * fast-path key a validator may draw per unit time; over budget it is pushed to
 * the slow path, which is slower for it and leaves the reservation intact for
 * everyone else. */
struct qkd_token_bucket {
	__u64 tokens;          /* in bits */
	__u64 capacity;
	__u64 refill_bits_per_s;
	__u64 last_refill_ns;
	__u64 throttled;       /* count of requests pushed to the slow path */
	__u64 starved_credits; /* leases that expired unused: daemon re-prioritises */
};

struct enforcer_stats {
	__u64 hits;
	__u64 misses;
	__u64 expired;
	__u64 short_key;
	__u64 throttled;
	__u64 gc_reclaimed;
	__u64 renewals;
	__u64 fast_ns;
};

struct cons_hdr {
	__u32 src_vid;
	__u32 dst_vid;
	__u32 view;
	__u32 bits_needed;
	__u64 t_send_ns;
	__u32 seq;
	__u32 flags;
} __attribute__((packed));

#endif /* __QKD_MAPS_H */
