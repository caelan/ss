import time
from collections import defaultdict

from ss.model.problem import reset_derived, apply, axiom_achievers, Operator
from ss.model.streams import StreamInstance

from ss.algorithms.incremental import solve_universe
from ss.algorithms.universe import Universe
from ss.model.functions import Atom, NegatedAtom, Literal, Operation, Increase, infer_evaluations, Head
from ss.utils import INF


def bound_stream_instances(universe):

    stream_from_head = {}
    while universe.stream_queue:
        instance = universe.stream_queue.popleft()
        for eval in infer_evaluations(instance.bound_atoms()):
            if eval.head not in stream_from_head:
                stream_from_head[eval.head] = instance
                universe.add_eval(eval)
    return stream_from_head


def recover_axioms_single(universe, plan):
    instances_from_effect = defaultdict(list)
    for axiom, args in universe.axiom_instances():
        ax = axiom.instantiate(args)
        instances_from_effect[ax.effect].append(ax)
    action_sequence = [universe.action_from_name[
        name].instantiate(args) for name, args in plan]
    state = apply(universe.evaluations, defaultdict(bool))
    reset_derived(universe.axioms_from_derived, state)
    for pre, act in [(a.preconditions, a) for a in action_sequence] + [(universe.problem.goal, None)]:
        for p in pre:
            if p.head.function not in universe.axioms_from_derived:
                continue
            if isinstance(p, Atom):
                for ax in instances_from_effect[p]:
                    if ax.applicable(state):
                        yield ax
                        break
                else:
                    raise RuntimeError('No supporting axioms')
            elif isinstance(p, NegatedAtom):
                universe.supporting(p, state)
                raise NotImplementedError()
            else:
                raise ValueError(p)
        if act is not None:
            yield act
            state = act.apply(state)


def retrace_supporters(op, axiom_from_eff):

    supporters = set()
    for pre in op.preconditions:
        if axiom_from_eff.get(pre, None) is None:
            supporters.add(pre)
        else:
            supporters |= retrace_supporters(
                axiom_from_eff[pre], axiom_from_eff)
    print op, op.preconditions, supporters
    return supporters


def required_heads(universe, plan):
    actions = [universe.action_from_name[
        name].instantiate(args) for name, args in plan]
    axioms = [axiom.instantiate(args)
              for axiom, args in universe.axiom_instances()]
    goal = Operator([], universe.problem.goal, [])
    state = apply(universe.evaluations, defaultdict(bool))

    heads = set()
    image = {}
    for act in actions + [goal]:
        axiom_from_eff = axiom_achievers(axioms, state)
        print
        preconditions = retrace_supporters(act, axiom_from_eff)
        for p in preconditions:
            assert isinstance(p, Literal)
            assert p.head.function not in universe.axioms_from_derived
            if p.head in image:
                assert image[p.head] == p.value
            else:
                heads.update(p.heads())
        for e in act.effects:
            if isinstance(e, Literal):
                image[e.head] = e.value
            elif isinstance(e, Increase):

                heads.update(e.heads())
            else:
                raise NotImplementedError(e)
        state = act.apply(state)
    return heads


def required_heads_old(universe, plan):
    supporting = set()
    literals = set()
    pairs = [(a.preconditions, a.effects) for a in recover_axioms(
        universe, plan)] + [(universe.problem.goal, [])]
    for preconditions, effects in pairs:
        for p in preconditions:
            assert isinstance(p, Literal)
            if p not in literals:
                supporting.update(p.heads())
        for e in effects:
            if isinstance(e, Literal):
                literals.add(e)
            elif isinstance(e, Operation):
                supporting.update(e.heads())
            else:
                raise NotImplementedError(e)
    return supporting


def retrace_streams(stream_from_head, evaluated, heads):
    streams = set()
    for head in heads:
        if head in evaluated:
            continue
        if head.function.fn is not None:
            stream = head
        elif head in stream_from_head:
            stream = stream_from_head[head]
        else:
            continue
        streams |= ({stream} | retrace_streams(stream_from_head, evaluated,
                                               (atom.head for atom in stream.domain())))
    return streams


def focused(problem, max_time=INF, verbose=False):

    start_time = time.time()
    num_iterations = 0
    num_epochs = 0
    evaluations = infer_evaluations(problem.initial)
    disabled = set()
    while (time.time() - start_time) < max_time:
        num_iterations += 1
        print '\nEpoch: {} | Iteration: {} | Time: {:.3f}'.format(num_epochs, num_iterations, time.time() - start_time)

        eager_universe = Universe(
            problem, evaluations, use_bounds=False, only_eager=True)

        evaluations = eager_universe.evaluations
        universe = Universe(problem, evaluations,
                            use_bounds=True, only_eager=False)

        stream_from_head = bound_stream_instances(universe)
        plan = solve_universe(universe, verbose=verbose)
        print 'Length: {} | Cost: {}'.format(len(plan), universe.get_cost(plan))
        print 'Plan:', plan
        if plan is None:
            if not disabled:
                return None
            for instance in disabled:
                instance.disabled = False
            disabled = set()
            num_epochs += 1
            continue

        evaluated = {e.head for e in evaluations}
        supporting_heads = required_heads(universe, plan)
        print 'Supporting:', supporting_heads
        useful_streams = retrace_streams(
            stream_from_head, evaluated, supporting_heads)
        print 'Useful:', [s.bound_repr() if isinstance(s, StreamInstance) else repr(s) for s in useful_streams]
        evaluable_streams = set(filter(lambda s: set(
            s.domain()) <= evaluations, useful_streams))
        print 'Evaluable:', [s.bound_repr() if isinstance(s, StreamInstance) else repr(s) for s in useful_streams]
        if not evaluable_streams:
            return plan

        for instance in evaluable_streams:
            if isinstance(instance, Head):
                evaluations.update(infer_evaluations([instance.get_eval()]))
            elif not instance.enumerated:
                evaluations.update(infer_evaluations(instance.next_atoms()))
                instance.disabled = True
                disabled.add(instance)
    return None
