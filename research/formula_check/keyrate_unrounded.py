"""Table keyrate recomputed with the unrounded Aptos view rate 26.794777665 (CHAIN_BUDGET.json)."""
v = 26.794777665041185
for n in (16, 32, 64, 84, 100):
    print(n, round(2*(n-1)*128*v/1e3, 1), round((n-3)*128*v/1e3, 1), round((n+1)*(n-1)*128*v/1e6, 2))
print("per pair n=84:", 166*128*v/3486, 7055*128*v/3486)
