import time
from collections import deque

from ss.algorithms.downward import DownwardProblem, solve_sas
from ss.algorithms.focused_utils import evaluate_eager, isolated_reset_fn, revisit_reset_fn
from ss.algorithms.incremental import solve_universe
from ss.algorithms.universe import Universe
from ss.model.functions import Increase, infer_evaluations, TotalCost, Atom, Literal, Head
from ss.model.problem import Operator, Axiom, get_length, get_cost
from ss.utils import INF


class BoundStream(object):

    def __init__(self, stream, bound_outputs, bound_atoms):
        self.stream = stream
        self.bound_outputs = bound_outputs
        self.bound_atoms = bound_atoms

    def __repr__(self):
        return '{}{}->{}'.format(self.stream.stream.name, self.stream.inputs, self.bound_outputs)


def bound_stream_instances(universe):

    bound_streams = []
    while universe.stream_queue:
        instance = universe.stream_queue.popleft()
        for outs in instance.bound_outputs():
            atoms = instance.substitute_graph(outs)
            if atoms:
                bound_streams.append(BoundStream(instance, outs, atoms))
            for eval in atoms:
                universe.add_eval(eval)
    return bound_streams


def literal_sequence(initial, actions):
    state = {}
    for action in [Operator([], [], initial)] + actions:
        assert not action.parameters
        for atom in action.effects:
            if isinstance(atom, Literal):
                atom.assign(state)
        yield state.copy()


def plan_preimage(universe, evaluations, plan):

    action_instances = [action.instantiate(args) for action, args in plan]
    lazy_states = list(literal_sequence(
        universe.evaluations, action_instances))
    real_states = list(literal_sequence(evaluations, action_instances))
    goal = Operator([], universe.problem.goal, [])
    axiom_instances = [axiom.instantiate(
        args) for axiom, args in universe.axiom_instances()]
    preimage = set()
    remapped_axioms = []
    for rs, ls, action in reversed(zip(real_states, lazy_states, action_instances + [goal])):
        preimage -= set(action.effects)

        derived = filter(
            lambda a: a.head.function in universe.axioms_from_derived, action.preconditions)
        preimage |= (set(action.preconditions) - set(derived))
        if derived:
            derived_map = {f: f.__class__(f.inputs)
                           for f in universe.axioms_from_derived}
            remap_fn = lambda a: Atom(
                Head(derived_map[a.head.function], a.head.args))
            preimage.update(map(remap_fn, derived))
            for ax in axiom_instances:
                preconditions = []
                for atom in ax.preconditions:
                    if atom.head.function in derived_map:
                        preconditions.append(remap_fn(atom))
                    elif ls.get(atom.head, False) != atom.value:
                        break
                    elif (atom.head not in rs) and (not atom.head.function.is_defined()):
                        preconditions.append(atom)

                else:
                    remapped_axioms.append(
                        Axiom([], preconditions, remap_fn(ax.effect)))
    return preimage, remapped_axioms


def solve_streams(universe, evaluations, plan, bound_streams, start_time, max_time):

    planner = 'ff-astar'

    if plan is None:
        return None
    if not plan:
        return []
    preimage, axioms = plan_preimage(universe, evaluations, plan)
    preimage_goal = preimage - evaluations
    if not preimage_goal:
        return []

    actions = []
    for bound_stream in bound_streams:
        instance = bound_stream.stream
        effort = instance.get_effort()
        assert effort != INF

        preconditions = [a for a in instance.domain() if a not in evaluations]
        effects = [a for a in bound_stream.bound_atoms if a not in evaluations]
        if instance.stream.eager and (len(effects) == 1):

            axioms.append(Axiom([], preconditions, effects[0]))
        else:
            action = Operator([], preconditions, effects +
                              [Increase(TotalCost(), effort)])
            action.bound_stream = bound_stream
            actions.append(action)

    downward_problem = DownwardProblem(
        evaluations, preimage_goal, actions, axioms)

    stream_plan = solve_sas(downward_problem, planner=planner,
                            max_time=(max_time - (time.time() - start_time)),
                            verbose=False, clean=True)
    if stream_plan is None:
        raise RuntimeError('Should be able to find a plan')

    return [a.bound_stream for a in stream_plan]


def disable_stream(disabled, instance):
    if not instance.disabled and not instance.enumerated:
        disabled.append(instance)
    instance.disabled = True


def call_streams(evaluations, disabled, bound_streams, revisit, single):
    if revisit:
        isolated_reset_fn(disabled, evaluations)
    if single:
        bound_streams = bound_streams[:1]
    evaluated = []
    for i, bound_stream in enumerate(bound_streams):
        instance = bound_stream.stream
        if set(instance.domain()) <= evaluations:
            evaluated.append(instance)
            new_atoms = instance.next_atoms()
            evaluations.update(new_atoms)
            disable_stream(disabled, instance)
            print i + 1, instance, new_atoms


def bind_call_streams(evaluations, disabled, bound_streams, revisit):

    if revisit:
        isolated_reset_fn(disabled, evaluations)
    bindings = {}
    for i, bound_stream in enumerate(bound_streams):
        old_instance = bound_stream.stream
        new_inputs = [bindings.get(inp, inp) for inp in old_instance.inputs]
        instance = old_instance.stream.get_instance(new_inputs)

        if not instance.enumerated and (set(instance.domain()) <= evaluations):

            for outputs in instance.next_outputs():
                evaluations.update(instance.substitute_graph(outputs))
                for b, o in zip(bound_stream.bound_outputs, outputs):
                    bindings[b] = o
            disable_stream(disabled, instance)
            print i + 1, instance

    print bindings


def dual_focused(problem, max_time=INF, max_cost=INF, terminate_cost=INF,
                 planner='ff-astar', reset_fn=revisit_reset_fn, single=False, bind=False, revisit=False, verbose=False):

    start_time = time.time()
    num_epochs = 1
    num_iterations = 0
    evaluations = infer_evaluations(problem.initial)
    disabled = deque()
    best_plan = None
    best_cost = INF
    search_time = 0
    stream_time = 0
    while (time.time() - start_time) < max_time:
        num_iterations += 1
        print '\nEpoch: {} | Iteration: {} | Disabled: {} | Cost: {} | '              'Search time: {:.3f} | Stream time: {:.3f} | Total time: {:.3f}'.format(
            num_epochs, num_iterations, len(disabled), best_cost, search_time, stream_time, time.time() - start_time)
        evaluations = evaluate_eager(problem, evaluations)
        universe = Universe(problem, evaluations,
                            use_bounds=True, only_eager=False)
        if not all(f.eager for f in universe.defined_functions):
            raise NotImplementedError(
                'Non-eager functions are not yet supported')
        bound_streams = bound_stream_instances(universe)
        t0 = time.time()

        plan = solve_universe(universe, planner=planner,
                              max_time=(max_time - (time.time() - start_time)),
                              max_cost=min(best_cost, max_cost), verbose=verbose)
        search_time += (time.time() - t0)
        cost = get_cost(plan, universe.evaluations)
        print 'Actions | Length: {} | Cost: {} | {}'.format(
            get_length(plan, universe.evaluations), cost, plan)
        t0 = time.time()
        streams = solve_streams(universe, evaluations,
                                plan, bound_streams, start_time, max_time)
        stream_time += (time.time() - t0)
        print 'Streams | Length: {} | {}'.format(get_length(streams, None), streams)
        if streams:
            if bind:
                bind_call_streams(evaluations, disabled, streams, revisit)
            else:
                call_streams(evaluations, disabled, streams, revisit, single)
            continue
        if (streams is not None) and (cost < best_cost):
            best_plan = plan
            best_cost = cost
        if (best_cost < terminate_cost) or not disabled:
            break
        if best_plan is None:
            isolated_reset_fn(disabled, evaluations)
        else:
            reset_fn(disabled, evaluations)
        num_epochs += 1
    return best_plan, evaluations
