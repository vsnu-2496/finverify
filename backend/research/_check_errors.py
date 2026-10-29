import json
data = json.load(open('data/condition_a_openai_gpt56_luna_results.json', 'r', encoding='utf-8'))
errs = [r for r in data if r['status'] == 'error' and r.get('error')]
print(f'Error count: {len(errs)}')
for e in errs[:10]:
    print(f"  {e['claim_id']}: {str(e['error'])[:200]}")
