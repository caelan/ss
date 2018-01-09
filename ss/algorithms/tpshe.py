from time import time
from fast_downward import read, write, safe_remove, INF
import os

DOMAIN_PATH = 'domain.pddl'
PROBLEM_PATH = 'problem.pddl'
OUTPUT_PATH = 'sas_plan'

ENV_VAR = 'TPSHE_PATH'
COMMAND = 'python {}bin/plan.py she {} {} --time {} --no-iterated'


def get_tpshe_root():
    if ENV_VAR not in os.environ:
        raise RuntimeError('Environment variable %s is not defined.' % ENV_VAR)
    return os.environ[ENV_VAR]


def run_tpshe(max_time, verbose):
    command = COMMAND.format(
        get_tpshe_root(), DOMAIN_PATH, PROBLEM_PATH, max_time)
    t0 = time()
    p = os.popen(command)
    if verbose:
        print command
    output = p.read()
    if verbose:
        print
        print output
        print 'Runtime:', time() - t0
    if not os.path.exists(OUTPUT_PATH):
        return None
    return read(OUTPUT_PATH)


def parse_solution(solution):
    lines = solution.split('\n')[:-2]
    plan = []
    for line in lines:
        entries = line.strip('( )').split(' ')
        name = entries[0][3:]
        plan.append((name, tuple(entries[1:])))
    return plan


def remove_paths():
    for p in [DOMAIN_PATH, PROBLEM_PATH, OUTPUT_PATH,
              'dom.pddl', 'ins.pddl', 'output', 'output.sas',
              'plan.validation', 'tdom.pddl', 'tins.pddl', 'tmp_sas_plan']:
        safe_remove(p)


def tpshe(domain_pddl, problem_pddl, max_time=30, verbose=True):
    remove_paths()
    write(DOMAIN_PATH, domain_pddl)
    write(PROBLEM_PATH, problem_pddl)
    solution = run_tpshe(max_time, verbose)
    if solution is None:
        return None
    if not verbose:
        remove_paths()
    return parse_solution(solution)
