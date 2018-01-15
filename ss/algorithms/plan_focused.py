import time
from collections import deque

from ss.algorithms.focused_utils import evaluate_eager, revisit_reset_fn
from ss.algorithms.incremental import solve_universe
from ss.algorithms.universe import Universe
from ss.model.functions import Predicate, Increase, infer_evaluations, TotalCost
from ss.model.problem import Action, Problem, get_length, get_cost
from ss.utils import INF


def bound_stream_instances(universe):
    abstract_evals = set()
    while universe.stream_queue:
        instance = universe.stream_queue.popleft()
        outputs_list = instance.bound_outputs()

        for outputs in outputs_list:
            params = instance.inputs + outputs
            universe.add_eval(instance.stream.predicate(*params))
            for atom in instance.substitute_graph(outputs):
                if atom not in universe.evaluations:
                    abstract_evals.add(atom)
                    universe.add_eval(atom)
    return abstract_evals


def plan_focused(problem, max_time=INF, terminate_cost=INF,
                 planner='ff-astar', reset_fn=revisit_reset_fn, single=False, verbose=False):
    start_time = time.time()
    num_iterations = 0
    num_epochs = 1
    evaluations = infer_evaluations(problem.initial)
    disabled = deque()

    stream_actions = []
    stream_axioms = []
    for stream in problem.streams:
        params = stream.inputs + stream.outputs
        stream.predicate = Predicate(params)
        preconditions = list(stream.domain) + [stream.predicate(*params)]

        action = Action(stream.name, params, preconditions,
                        list(stream.graph) + [Increase(TotalCost(), 1)])
        action.stream = stream
        stream_actions.append(action)

    stream_problem = Problem([], problem.goal, problem.actions + stream_actions,
                             problem.axioms + stream_axioms, problem.streams, objective=TotalCost())
    best_plan = None
    best_cost = INF
    while (time.time() - start_time) < max_time:
        num_iterations += 1
        print 'Epoch: {} | Iteration: {} | Disabled: {} | Cost: {} | '              'Time: {:.3f}'.format(num_epochs, num_iterations, len(disabled), best_cost, time.time() - start_time)
        evaluations = evaluate_eager(problem, evaluations)
        universe = Universe(stream_problem, evaluations,
                            use_bounds=True, only_eager=False)
        if not all(f.eager for f in universe.defined_functions):
            raise NotImplementedError(
                'Non-eager functions are not yet supported')

        abstract_evals = bound_stream_instances(universe)
        universe.evaluations -= abstract_evals
        plan = solve_universe(universe, planner=planner, verbose=verbose)
        if plan is None:
            if not disabled:
                break
            reset_fn(disabled, evaluations)
            num_epochs += 1
            continue

        action_instances = []
        stream_instances = []
        for action, args in plan:
            if action not in stream_actions:
                action_instances.append((action, args))
                continue
            inputs = args[:len(action.stream.inputs)]
            stream_instances.append(action.stream.get_instance(inputs))
        print 'Length: {} | Cost: {} | Streams: {}'.format(
            get_length(plan, universe.evaluations), get_cost(plan, universe.evaluations), len(stream_instances))

        print 'Actions:', action_instances
        if not stream_instances:
            cost = get_cost(plan, universe.evaluations)
            if cost < best_cost:
                best_plan = plan
                best_cost = cost
            if (best_cost != INF) and (best_cost <= terminate_cost):
                break
            if not disabled:
                break
            reset_fn(disabled, evaluations)
            num_epochs += 1
            continue

        if single:
            stream_instances = stream_instances[:1]
        print 'Streams:', stream_instances
        evaluated = []
        for i, instance in enumerate(stream_instances):
            if set(instance.domain()) <= evaluations:
                new_atoms = infer_evaluations(instance.next_atoms())

                evaluations.update(new_atoms)
                instance.disabled = True
                if not instance.enumerated:
                    disabled.append(instance)
                evaluated.append(instance)
        if verbose:
            print 'Evaluated:', evaluated
        assert evaluated

    return best_plan, evaluations
