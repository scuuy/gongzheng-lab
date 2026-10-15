import argparse
import json


def main():
    p = argparse.ArgumentParser(description='工证 Lab · 原生工程重放与验收')
    sub = p.add_subparsers(dest='command', required=True)
    g = sub.add_parser('generate'); g.add_argument('--out', default='examples')
    r = sub.add_parser('regression'); r.add_argument('--examples', default='examples'); r.add_argument('--out', default='runs/regression')
    v = sub.add_parser('verify'); v.add_argument('project'); v.add_argument('--out', required=True); v.add_argument('--requirements')
    m = sub.add_parser('apply-proposal'); m.add_argument('project'); m.add_argument('proposal'); m.add_argument('--out', required=True)
    f = sub.add_parser('repair'); f.add_argument('project'); f.add_argument('--out', required=True)
    s = sub.add_parser('serve'); s.add_argument('--port', type=int, default=8770)
    a = p.parse_args()
    if a.command == 'generate':
        from gongzheng.examples import generate
        generate(a.out)
    elif a.command == 'regression':
        from gongzheng.examples import regression
        regression(a.examples, a.out)
    elif a.command == 'verify':
        from gongzheng.verify import verify
        print(json.dumps(verify(a.project, a.out, a.requirements), ensure_ascii=False))
    elif a.command == 'apply-proposal':
        from gongzheng.proposal import apply_proposal
        print(json.dumps(apply_proposal(a.project, a.proposal, a.out), ensure_ascii=False))
    elif a.command == 'repair':
        from gongzheng.repair import repair
        print(json.dumps(repair(a.project, a.out), ensure_ascii=False))
    elif a.command == 'serve':
        from gongzheng.server import serve
        serve(a.port)


if __name__ == '__main__':
    main()
