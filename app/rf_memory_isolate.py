"""Explicit reviewed *5 caller-isolation plan/apply; never called by installer."""
import argparse
import hashlib
import json
import os
from rf_memories import Config


def apply_reviewed(node,digest):
    from system_service import STATE, ETC, load_state, save_state, config_drift, cli
    from favorites_store import Store
    def reload():
        output=cli('module reload app_rpt.so')
        if any(s in output.lower() for s in ('failed','not found','does not support','error')):
            raise ValueError('Asterisk rejected reload.')
    # Same lock ordering as favorites saves and station configuration regeneration.
    with Store(STATE/'favorites.json')._lock():
        state=load_state()
        if config_drift(state):raise ValueError('Existing configuration drift must be reviewed before isolation; no hashes adopted.')
        changed=False
        def reconcile():
            nonlocal changed
            if state.get('config_hashes'):
                revised=dict(state)
                revised['config_hashes']={name:hashlib.sha256((ETC/name).read_bytes()).hexdigest() for name in state['config_hashes']}
                changed=True
                save_state(revised)
        try:
            return Config(ETC/'rpt.conf',node,reload,STATE/'rf-memories.lock').apply_isolation(digest,STATE/'rf-isolation.json',reconcile)
        except BaseException:
            if changed:save_state(state)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',required=True)
    parser.add_argument('--apply-reviewed-digest')
    args=parser.parse_args()
    if args.apply_reviewed_digest:
        if os.geteuid()!=0:raise SystemExit('Apply requires the station administrator.')
        result=apply_reviewed(args.node,args.apply_reviewed_digest)
    else:result=Config(node=args.node).isolation_plan()
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
