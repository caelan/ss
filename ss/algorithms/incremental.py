import time

from ss.algorithms.fast_downward import fast_downward
from ss.algorithms.universe import Universe
from ss.utils import INF


def evaluate_stream_instances(universe, max_evals):
    num_evals = 0
    while universe.stream_queue and (num_evals < max_evals):
        num_evals += 1
        instance = universe.stream_queue.popleft()
        for eval in instance.next_atoms():
            universe.add_eval(eval)
        if not instance.enumerated:
            universe.stream_queue.append(instance)


def solve_universe(universe, **kwargs):

    domain_pddl, problem_pddl = universe.pddl()
    plan = fast_downward(domain_pddl, problem_pddl, **kwargs)

    return universe.convert_plan(plan)


def incremental(problem, max_time=INF, verbose=False):
    start_time = time.time()
    num_iterations = 0
    universe = Universe(problem, problem.initial,
                        use_bounds=False, only_eager=False)
    while universe.stream_queue and ((time.time() - start_time) < max_time):
        num_iterations += 1
        print 'Iteration {})'.format(num_iterations)
        evaluate_stream_instances(universe, len(universe.stream_queue))
        plan = solve_universe(universe, verbose=verbose)
        if plan is not None:
            return plan
    return None


def exhaustive(problem, max_time=INF, verbose=False):
    start_time = time.time()
    universe = Universe(problem, problem.initial,
                        use_bounds=False, only_eager=False)

    while universe.stream_queue and ((time.time() - start_time) < max_time):
        evaluate_stream_instances(universe, 1)
    return solve_universe(universe, verbose=verbose)
