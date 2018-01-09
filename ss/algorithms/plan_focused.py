import time

from ss.model.problem import Action, Problem

from ss.algorithms.incremental import solve_universe
from ss.algorithms.universe import Universe, get_length
from ss.model.functions import Predicate, Increase, infer_evaluations, TotalCost
from ss.utils import INF


def make_stream_action(stream):
    params = stream.inputs + stream.outputs
    stream.predicate = Predicate(params)
    action = Action(stream.name, params,
                    list(stream.domain) + [stream.predicate(*params)],
                    list(stream.graph) + [Increase(TotalCost(), 1)])
    action.stream = stream
    return action


def bound_stream_instances(universe):
    instances = []
    abstract_evals = set()
    while universe.stream_queue:
        instance = universe.stream_queue.popleft()
        instances.append(instance)
        outputs_list = instance.bound_outputs()

        for outputs in outputs_list:
            params = instance.inputs + outputs
            universe.add_eval(instance.stream.predicate(*params))
            for atom in instance.substitute_graph(outputs):
                if atom not in universe.evaluations:

                    abstract_evals.add(atom)
                    universe.add_eval(atom)

    return abstract_evals


def plan_focused(problem, max_time=INF, planner='ff-astar', single=False, verbose=False):
    start_time = time.time()
    num_iterations = 0
    num_epochs = 1
    evaluations = infer_evaluations(problem.initial)
    disabled = set()

    stream_actions = map(make_stream_action, problem.streams)
    print stream_actions

    stream_problem = Problem([], problem.goal,
                             problem.actions + stream_actions, problem.axioms,
                             problem.streams, objective=TotalCost())

    while (time.time() - start_time) < max_time:
        num_iterations += 1
        print '\nEpoch: {} | Iteration: {} | Disabled: {} | Time: {:.3f}'.format(num_epochs, num_iterations,
                                                                                 len(disabled), time.time() - start_time)

        eager_universe = Universe(
            problem, evaluations, use_bounds=False, only_eager=True)

        evaluations = eager_universe.evaluations
        universe = Universe(stream_problem, evaluations,
                            use_bounds=True, only_eager=False)

        abstract_evals = bound_stream_instances(universe)
        universe.evaluations -= abstract_evals
        plan = solve_universe(universe, planner=planner, verbose=verbose)
        print 'Length: {} | Cost: {}'.format(get_length(plan), universe.get_cost(plan))
        print 'Plan:', plan
        if plan is None:
            if not disabled:
                return None
            for instance in disabled:
                instance.disabled = False
            disabled = set()
            num_epochs += 1
            continue

        action_instances = []
        stream_instances = []
        for name, args in plan:
            action = universe.action_from_name[name]
            if action not in stream_actions:
                action_instances.append((action, args))
                continue
            inputs = args[:len(action.stream.inputs)]
            stream_instances.append(action.stream.get_instance(inputs))
        print 'Actions:', action_instances
        if not stream_instances:
            return plan
        if single:
            stream_instances = stream_instances[:1]
        print 'Streams:', stream_instances
        evaluated = []
        for i, instance in enumerate(stream_instances):
            if set(instance.domain()) <= evaluations:

                new_atoms = infer_evaluations(instance.next_atoms())
                print i, instance, new_atoms
                evaluations.update(new_atoms)
                instance.disabled = True
                disabled.add(instance)
                evaluated.append(instance)
        print 'Evaluated:', evaluated
        assert evaluated

    return None
