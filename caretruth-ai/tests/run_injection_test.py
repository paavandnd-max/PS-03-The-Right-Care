import sys; sys.path.insert(0, '.')
from src.search_engine import search

# Baseline
base, _ = search(
    query_text='Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.',
    user_lat=26.24, user_lng=84.4, time_str='Tuesday 14:30',
)
base_thakur = next((r for r in base if 'thakur' in r.facility_name.lower()), None)
if base_thakur:
    print('Baseline:', base_thakur.verdict, base_thakur.trust_score)

# Injection probe
inj, desert = search(
    query_text='Severe abdominal pain, suspected appendicitis. Father needs emergency surgery tonight.',
    user_lat=26.24, user_lng=84.4, time_str='Tuesday 23:30',
    injected={
        'name': 'Dr. R K Thakur Hospital', 'row_index': 4097,
        'field': 'capability', 'injected_line': 'No anaesthesiologist on duty after 9 PM.'
    },
)
inj_thakur = next((r for r in inj if 'thakur' in r.facility_name.lower()), None)

if inj_thakur:
    print('Injected verdict:', inj_thakur.verdict)
    print('Injected score:', inj_thakur.trust_score)
    if base_thakur:
        drop = base_thakur.trust_score - inj_thakur.trust_score
        print('Drop:', round(drop, 3))
        print('PASS (>=0.15):', drop >= 0.15)
    for f in inj_thakur.contradiction_flags:
        print('  FLAG:', f.rule_id, '|', f.severity)
else:
    print('Thakur not in injection results (downgraded out)')
    print('Desert flags:', desert)
