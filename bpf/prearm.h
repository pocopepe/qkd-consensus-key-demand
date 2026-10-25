/* Shared layout between the XDP data plane and the userspace control plane. */
#ifndef __PREARM_H
#define __PREARM_H

#define CONSENSUS_PORT 7788
#define KEY_ID_BYTES   16

/* Ordered validator pair; ordering imposed kernel-side so both planes agree. */
struct pair_key {
	__u32 lo;
	__u32 hi;
};

/* 32 bytes; with the 8-byte key that is 40 bytes per slot, so a memory
 * budget converts directly into M_max. */
struct prearm_val {
	__u8  key_id[KEY_ID_BYTES];
	__u32 offset;      /* byte offset into the key stream already consumed */
	__u32 bits_left;   /* remaining pre-positioned key */
	__u64 expiry_ns;   /* bpf_ktime_get_ns() deadline; 0 = no expiry */
};

/* Per-CPU counters; lets the control plane read hit rate without
 * instrumenting the consensus process. */
struct prearm_stats {
	__u64 hits;
	__u64 misses;
	__u64 expired;
	__u64 short_key;
	__u64 fast_ns;     /* accumulated in-kernel service time on hits */
};

/* Consensus message carried over UDP. flags bit 0 marks a response that the
 * data plane generated without ever waking userspace. */
#define CONS_FLAG_RESPONSE 0x1
#define CONS_FLAG_FASTPATH 0x2

struct cons_hdr {
	__u32 src_vid;
	__u32 dst_vid;
	__u32 view;
	__u32 bits_needed;
	__u64 t_send_ns;
	__u32 seq;
	__u32 flags;
} __attribute__((packed));

#endif /* __PREARM_H */
