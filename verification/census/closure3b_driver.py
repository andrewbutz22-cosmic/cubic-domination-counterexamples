import sys, time, json
import closure3b
idxs = [int(x) for x in sys.argv[1].split(',')]
budget = float(sys.argv[2]); t0 = time.time()
for i in idxs:
    left = budget - (time.time() - t0)
    if left < 15: break
    st = closure3b.run(i, 'census_tight_15_20.json', left)
    s = {k: v for k, v in st.items() if k not in ('unsat_certs', 'outside')}
    s.update(index=i, classes_reached=len(st['unsat_certs']), outside=len(st['outside']))
    print(json.dumps(s))
    if st['done']:
        open('closure3b_results.jsonl', 'a').write(json.dumps({**s, 'outside_detail': st['outside']}) + '\n')
    else:
        break
