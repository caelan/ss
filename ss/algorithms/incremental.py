import time

from ss.algorithms.fast_downward import fast_downward
from ss.algorithms.universe import Universe
from ss.utils import INF
from ss.model.problem import get_cost


def evaluate_stream_instances(universe, max_evals):
    num_evals = 0
    while universe.stream_queue and (num_evals < max_evals):
        num_evals += 1
        instance = universe.stream_queue.popleft()
        new_atoms = instance.next_atoms()

        for eval in new_atoms:
            universe.add_eval(eval)
        if not instance.enumerated:
            universe.stream_queue.append(instance)


def solve_universe(universe, **kwargs):
    if not universe.problem.goal:
        return []

    domain_pddl, problem_pddl = universe.pddl()
    plan = fast_downward(domain_pddl, problem_pddl, **kwargs)

    return universe.convert_plan(plan)


def incremental(problem, max_time=INF, max_cost=INF, terminate_cost=INF, verbose=False):

    start_time = time.time()
    num_iterations = 0
    universe = Universe(problem, problem.initial,
                        use_bounds=False, only_eager=False)
    best_plan = None
    best_cost = INF
    while (time.time() - start_time) < max_time:
        num_iterations += 1
        remaining_time = max_time - (time.time() - start_time)
        print 'Iteration: {} | Evaluations: {} | Cost: {} | '              'Remaining: {:.3}'.format(num_iterations, len(universe.evaluations), best_cost, remaining_time)
        plan = solve_universe(universe, max_time=remaining_time,
                              max_cost=min(best_cost, max_cost), verbose=verbose)
        cost = get_cost(plan, universe.evaluations)
        if cost < best_cost:
            best_plan = plan
            best_cost = cost
        if (best_cost != INF) and (best_cost <= terminate_cost):
            break
        if not universe.stream_queue:
            break
        evaluate_stream_instances(universe, len(universe.stream_queue))
    return best_plan, universe.evaluations


def exhaustive(problem, max_time=INF, max_cost=INF, search_time=5, verbose=False):
    stream_time = max_time - search_time
    start_time = time.time()
    universe = Universe(problem, problem.initial,
                        use_bounds=False, only_eager=False)
    while universe.stream_queue and ((time.time() - start_time) < stream_time):
        evaluate_stream_instances(universe, 1)
    plan = solve_universe(universe, max_time=search_time,
                          max_cost=max_cost, verbose=verbose)
    return plan, universe.evaluations


def finite(problem, max_cost=INF, search_time=INF, verbose=False):
    universe = Universe(problem, problem.initial,
                        use_bounds=False, only_eager=False)
    evaluate_stream_instances(universe, INF)
    plan = solve_universe(universe, max_time=search_time,
                          max_cost=max_cost, verbose=verbose)
    return plan, universe.evaluations
