"""Limitations: 'by the Aptos stakes the heaviest pair draws 2.9 times the mean'.
Expected demand of pair {u,v} per view under iid leaders = 2(s_u+s_v); mean over pairs = 4/n."""
import os
import json, glob
r = []
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'realworld', 'raw_v3', 'epoch_*.json'))):
    vp = sorted((int(x['voting_power']) for x in json.load(open(f))['validators']), reverse=True)
    n = len(vp); s = [x/sum(vp) for x in vp]
    r.append(n*(s[0]+s[1])/2)
print(f"heaviest pair / mean: {min(r):.3f} .. {max(r):.3f} over {len(r)} epochs")
