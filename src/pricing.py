"""Scale decision: model outputs for one scan -> one rule, one message, one price (rules 1-7, checked in order; first match wins)."""
from pathlib import Path
import math
import numpy as np, pandas as pd, yaml

TIERS = ['A', 'B', 'C', 'D']

def load(cfg_dir):
    """rules.yaml, prices per kg, and the validation freshness errors used for confidence (per produce type if calibrated)."""
    cfg_dir = Path(cfg_dir)
    rules = yaml.safe_load((cfg_dir / 'rules.yaml').read_text())
    prices = pd.read_csv(cfg_dir / 'prices.csv').set_index('produce').price_per_kg.to_dict()
    npz, npy = cfg_dir / 'fresh_residuals.npz', cfg_dir / 'fresh_residuals.npy'
    res = dict(np.load(npz)) if npz.exists() else (np.load(npy) if npy.exists() else None)
    return rules, prices, res

def tier_idx(f, rules):
    m = [rules['tiers'][t]['min'] for t in 'ABC']; f = np.asarray(f, dtype=float)
    return np.select([f >= m[0], f >= m[1], f >= m[2]], [0, 1, 2], 3)

def _errors_for(residuals, produce, min_n=30):
    """This type's validation errors if it has enough, otherwise all types' ('_all')."""
    if isinstance(residuals, dict):
        r = residuals.get(produce)
        return r if r is not None and len(r) >= min_n else residuals.get('_all')
    return residuals

def fresh_conf(f, residuals, rules, produce=None):
    """Share of validation errors (for this produce type) that keep an item graded f in the same tier."""
    r = _errors_for(residuals, produce)
    if r is None or len(r) == 0: return 1.0
    return float(np.mean(tier_idx(np.clip(f + r, 0, 1), rules) == tier_idx(f, rules)))

def decide(scan, rules, prices, residuals=None):
    """scan: selected_type, weight_kg, failed_scans, items=[{box:[x0,y0,x1,y1], produce, det_conf, freshness, days_left, energy}]."""
    th, msg, items = rules['thresholds'], rules['messages'], [dict(i) for i in scan.get('items', [])]
    for it in items:                                       # confidence uses the shopper's selected type (detector types are unreliable)
        it['tier'] = TIERS[int(tier_idx(it['freshness'], rules))]
        it['fresh_conf'] = fresh_conf(it['freshness'], residuals, rules, scan.get('selected_type'))
    out = dict(rule_id=None, message=None, staff_alert=False, review=False, price=None, bag_freshness=None, bag_tier=None,
               fields={}, items=items, failed_scans=int(scan.get('failed_scans', 0)), thresholds=dict(th))

    def fail(rule_id):                                     # rules 1, 2 and 6 count as a failed scan
        out.update(rule_id=rule_id, message=msg['r1'] if rule_id == 1 else msg['r2']); out['failed_scans'] += 1
        if rule_id != 1 and out['failed_scans'] >= th['failed_scans_for_staff']:
            out['message'] += ' ' + msg['r2_staff']; out['staff_alert'] = True
        return out

    if not items or any(it.get('energy', -math.inf) > th['e_thr'] for it in items):
        return fail(1)
    if any(it['fresh_conf'] < th['tau_conf'] for it in items):
        return fail(2)
    sure_types = {it['produce'] for it in items if it['det_conf'] >= th['tau_det']}
    if len(sure_types) >= 2:
        out.update(rule_id=3, message=msg['r3']); return out
    other = [it for it in items if it['produce'] != scan['selected_type']]
    if any(it['det_conf'] >= th['tau_det'] for it in other):
        det = max(other, key=lambda it: it['det_conf'])['produce']
        out.update(rule_id=4, message=msg['r4'].format(detected=det)); return out
    out['review'] = bool(other)                            # below tau_det the shopper's choice stands; logged for review
    rotten = [it for it in items if it['tier'] == 'D']
    if any(it['fresh_conf'] >= th['tau_rotten'] for it in rotten):
        out.update(rule_id=5, message=msg['r5'], staff_alert=True); return out
    if rotten:
        return fail(6)                                     # never flag rot on a guess: treated as "scan again"
    area = np.array([max(1.0, (b[2] - b[0]) * (b[3] - b[1])) for b in (it['box'] for it in items)])
    f = float(np.average([it['freshness'] for it in items], weights=area))
    days = float(np.average([it.get('days_left', 0.0) for it in items], weights=area))
    tier = TIERS[int(tier_idx(f, rules))]; t = rules['tiers'][tier]
    if tier == 'D':                                        # every item C or better, but the weighted bag fell into D
        return fail(6)
    ppk = float(prices[scan['selected_type']]); disc = float(t['discount'])
    total = round(scan['weight_kg'] * ppk * (1 - disc) + 1e-9, 2)
    out.update(rule_id=7, price=total, bag_freshness=round(f, 4), bag_tier=tier,
               message=(t['message'] or '').format(days=max(1, int(days))) or None,
               fields=dict(weight_kg=scan['weight_kg'], price_per_kg=ppk, discount_pct=round(100 * disc), total=total))
    return out
