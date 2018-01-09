from time import time
from ss.utils import INF
import sys
import os

DOMAIN_INPUT = 'domain.pddl'
PROBLEM_INPUT = 'problem.pddl'
TRANSLATE_OUTPUT = 'output.sas'
SEARCH_OUTPUT = 'sas_plan'

ENV_VAR = 'FD_PATH'
FD_BIN = 'bin'
TRANSLATE_DIR = 'translate/'
SEARCH_COMMAND = 'downward %s < '


SEARCH_OPTIONS = {
    'dijkstra': '--heuristic "h=blind(transform=adapt_costs(cost_type=PLUSONE))" --search "astar(h,cost_type=NORMAL,max_time=%s,bound=%s)"',

    'max-astar': '--heuristic "h=hmax(transform=adapt_costs(cost_type=NORMAL))" --search "astar(h,cost_type=NORMAL,max_time=%s,bound=%s)"',

    'ff-astar': '--heuristic "h=ff(transform=adapt_costs(cost_type=NORMAL))" --search "astar(h,cost_type=NORMAL,max_time=%s,bound=%s)"',
    'ff-eager': '--heuristic "hff=ff(transform=adapt_costs(cost_type=PLUSONE))" '
    '--search "eager_greedy([hff],preferred=[hff],max_time=%s,bound=%s)"',
}


def read(filename):
    with open(filename, 'r') as f:
        return f.read()


def write(filename, string):
    with open(filename, 'w') as f:
        f.write(string)


def safe_remove(p):
    if os.path.exists(p):
        os.remove(p)


def get_fd_root():
    if ENV_VAR not in os.environ:
        raise RuntimeError('Environment variable %s is not defined.' % ENV_VAR)
    return os.environ[ENV_VAR]


def run_translate(verbose):
    t0 = time()
    translate_path = os.path.join(get_fd_root(), FD_BIN, TRANSLATE_DIR)
    if translate_path not in sys.path:
        sys.path.append(translate_path)

    temp_argv = sys.argv[:]
    sys.argv = sys.argv[:1] + [DOMAIN_INPUT, PROBLEM_INPUT]
    import translate
    sys.argv = temp_argv

    if verbose:
        print '\nTranslate command: import translate; translate.main()'
        translate.main()
        print 'Translate runtime:', time() - t0
        return
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            translate.main()
        finally:
            sys.stdout = old_stdout


def run_fast_downward(planner, max_time, max_cost, verbose):
    if max_time == INF:
        max_time = 'infinity'
    elif isinstance(max_time, float):
        max_time = int(max_time)
    if max_cost == INF:
        max_cost = 'infinity'
    elif isinstance(max_cost, float):
        max_cost = int(max_cost)
    run_translate(verbose)

    t0 = time()
    search = os.path.join(get_fd_root(), FD_BIN,
                          SEARCH_COMMAND) + TRANSLATE_OUTPUT
    planner_config = SEARCH_OPTIONS[planner] % (max_time, max_cost)
    command = search % planner_config
    if verbose:
        print '\nSearch command:', command
    p = os.popen(command)
    output = p.read()
    if verbose:
        print output[:-1]
        print 'Search runtime:', time() - t0
    if not os.path.exists(SEARCH_OUTPUT):
        return None
    return read(SEARCH_OUTPUT)


def parse_solution(solution):
    lines = solution.split('\n')[:-2]
    plan = []
    for line in lines:
        entries = line.strip('( )').split(' ')
        plan.append((entries[0], tuple(entries[1:])))
    return plan


def remove_paths():
    for p in [DOMAIN_INPUT, PROBLEM_INPUT, TRANSLATE_OUTPUT, SEARCH_OUTPUT]:
        safe_remove(p)


def fast_downward(domain_pddl, problem_pddl, planner='max-astar', max_time=INF, max_cost=INF,
                  verbose=False, clean=False):
    remove_paths()
    write(DOMAIN_INPUT, domain_pddl)
    write(PROBLEM_INPUT, problem_pddl)
    solution = run_fast_downward(planner, max_time, max_cost, verbose)
    if clean:
        remove_paths()
    if solution is None:
        return None
    return parse_solution(solution)
