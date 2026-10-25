"""Cross-check of 'with any relay delay it serves 5.7% (Aptos), 2.4% round-robin':
share of view-t demand on S(t-2) under iid stake-weighted leaders (A8, chained rotation)."""
import os
import json, glob
def stale(s):
    n = len(s); q = sum(x*x for x in s)
    # X = {x1,x2} leaders of t-2,t-1 ; y a hub of view t, independent of X
    tot = 0.0
    for y, sy in enumerate(s):
        p_in = 1 - (1 - sy)**2                       # y in X
        # E[|X| 1(y not in X)]: X distinct (size 2) or x1=x2 (size 1), both != y
        p_same_not_y = q - sy*sy                     # x1=x2!=y
        p_notin = (1 - sy)**2
        e_size = 2*(p_notin - p_same_not_y) + 1*p_same_not_y
        tot += sy*(p_in*(n-1) + e_size)
    return 2*tot/(2*(n-1))
vals = []
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'realworld', 'raw_v3', 'epoch_*.json'))):
    vp = [int(x['voting_power']) for x in json.load(open(f))['validators']]; s = [x/sum(vp) for x in vp]
    vals.append(stale(s))
print(f"Aptos stake model: {min(vals):.4f}..{max(vals):.4f}; equal stakes n=84: {stale([1/84]*84):.4f}; round-robin 2/(n-1) = {2/83:.4f}")
