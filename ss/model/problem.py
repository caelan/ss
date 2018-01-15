from ss.model.functions import TotalCost
from ss.to_pddl import pddl_conjunction
from functions import Head, process_parameters, check_parameters, is_parameter, Atom, initialize
from ss.to_pddl import pddl_parameter
from collections import defaultdict, deque

from ss.utils import INF


def applicable(preconditions, state):
    for p in preconditions:
        if not p.holds(state):
            return False
    return True


def apply(effects, state):
    new_state = state.copy()
    for e in effects:
        e.assign(new_state)
    return new_state


def state_sequence(initial, actions):

    states = [apply(initial, {})]
    for action in actions:
        assert not action.parameters
        states.append(action.apply(states[-1]))
    return states


def is_solution(evals, plan, goal):

    state = defaultdict(bool)
    instances = [Initial(evals)] + [action.instantiate(args)
                                    for action, args in plan] + [Goal(goal)]
    for instance in instances:
        if not instance.applicable(state):
            return False
        state = instance.apply(state)
    return True


class Operator(object):

    def __init__(self, param, pre, eff):
        self.parameters = process_parameters(param)
        self.preconditions = tuple(pre)
        self.effects = tuple(eff)
        assert len(self.parameters) == len(set(self.parameters))
        assert set(self.parameters) <= self.arguments()
        assert {a for a in self.arguments() if is_parameter(a)
                } <= set(self.parameters)

    def arguments(self):
        return {a for e in (self.preconditions + self.effects) for h in e.heads() for a in h.args}

    def constants(self):
        return self.arguments() - set(self.parameters)

    def functions(self):
        return {h.function for e in (self.preconditions + self.effects) for h in e.heads()}

    def applicable(self, state):
        return applicable(self.preconditions, state)

    def apply(self, state):
        return apply(self.effects, state)

    def __repr__(self):
        return 'Op({},{},{})'.format(list(self.parameters), list(self.preconditions), list(self.effects))


class Initial(Operator):

    def __init__(self, eff):
        super(Initial, self).__init__([], [], eff)


class Goal(Operator):

    def __init__(self, pre):
        super(Goal, self).__init__([], pre, [])


class Action(Operator):

    def __init__(self, name, param, pre, eff):
        super(Action, self).__init__(param, pre, eff)
        self.name = name.lower()

    def instantiate(self, values):
        param_mapping = dict(zip(self.parameters, values))
        return self.__class__(self.name, tuple(),
                              [p.substitute(param_mapping)
                               for p in self.preconditions],
                              [e.substitute(param_mapping) for e in self.effects])

    def substitute_constants(self, mapping):
        constant_mapping = {c: mapping[c]
                            for c in self.constants() if c in mapping}
        return self.__class__(self.name, self.parameters,
                              [p.substitute(constant_mapping)
                               for p in self.preconditions],
                              [e.substitute(constant_mapping) for e in self.effects])

    def pddl(self):
        return '\t(:action {}\n'                '\t\t:parameters ({})\n'                '\t\t:precondition {}\n'                '\t\t:effect {})'.format(self.name,
                                                                                                                                                         ' '.join(
                                                                                                                                                             map(pddl_parameter, self.parameters)),
                                                                                                                                                         pddl_conjunction(
                                                                                                                                                             self.preconditions),
                                                                                                                                                         pddl_conjunction(self.effects))

    def __repr__(self):
        return self.name


class DurativeAction(Action):

    def pddl(self):
        return '\t(:durative-action {}\n'                '\t\t:parameters ({})\n'                '\t\t:duration (= ?duration 1)\n'                '\t\t:condition (over all {})\n'                '\t\t:effect (at end {}))'.format(self.name,
                                                                                                                                                                                                                                    ' '.join(
                                                                                                                                                                                                                                        map(pddl_parameter, self.parameters)),
                                                                                                                                                                                                                                    pddl_conjunction(
                                                                                                                                                                                                                                        self.preconditions),
                                                                                                                                                                                                                                    pddl_conjunction(self.effects))


class Axiom(Operator):

    def __init__(self, param, pre, eff):
        super(Axiom, self).__init__(param, pre, [eff])
        self.effect = eff

    def instantiate(self, values):
        param_mapping = dict(zip(self.parameters, values))
        return self.__class__(tuple(),
                              [p.substitute(param_mapping)
                               for p in self.preconditions],
                              self.effect.substitute(param_mapping))

    def substitute_constants(self, mapping):
        constant_mapping = {c: mapping[c]
                            for c in self.constants() if c in mapping}
        return self.__class__(self.parameters,
                              [p.substitute(constant_mapping)
                               for p in self.preconditions],
                              self.effect.substitute(constant_mapping))

    def __repr__(self):
        return repr(self.effect)


class Problem(object):

    def __init__(self, initial, goal, actions, axioms, streams, objective=None):
        self.initial = sorted(initial)

        self.goal = goal
        self.actions = actions
        self.axioms = axioms
        self.streams = streams
        self.objective = objective

    def get_action(self, name):
        for action in self.actions:
            if action.name == name:
                return action
        return None

    def is_temporal(self):

        return any(isinstance(action, DurativeAction) for action in self.actions)

    def fluents(self):
        fluents = set()
        for action in self.actions:
            for e in action.effects:
                fluents.add(e.head.function)
        return fluents

    def derived(self):
        return {ax.effect.head.function for ax in self.axioms}

    def dump(self):
        print 'Initial'
        dump_evaluations(self.initial)

    def __repr__(self):
        return '{}\n'               'Initial: {}\n'               'Goal: {}\n'               'Actions: {}\n'               'Axioms: {}\n'               'Streams: {}\n'.format(self.__class__.__name__,
                                                                                                                                                                               self.initial, self.goal,
                                                                                                                                                                               self.actions, self.axioms, self.streams)


def reset_derived(derived, state):
    for head in list(state):
        if head.function in derived:
            state[head] = False
        if state[head] is False:
            del state[head]


def apply_axioms_slow(axiom_instances, state):

    for axiom in axiom_instances:
        if axiom.applicable(state):
            axiom.effect.assign(state)


def axiom_achievers(axiom_instances, state):

    axioms_from_pre = defaultdict(list)
    for ax in axiom_instances:
        for p in ax.preconditions:
            assert isinstance(p, Atom)
            axioms_from_pre[p].append(ax)

    axiom_from_eff = {}
    queue = deque()
    for head, val in state.items():
        eval = initialize(head, val)
        if isinstance(eval, Atom) and (eval not in axiom_from_eff):
            axiom_from_eff[eval] = None
            queue.append(eval)
    while queue:
        pre = queue.popleft()
        for ax in axioms_from_pre[pre]:
            if (ax.effect not in axiom_from_eff) and all(p in axiom_from_eff for p in ax.preconditions):

                axiom_from_eff[ax.effect] = ax
                queue.append(ax.effect)
    return axiom_from_eff


def supporting_axioms_helper(goal, axiom_from_eff, supporters):

    axiom = axiom_from_eff[goal]
    if (axiom is None) or (axiom in supporters):
        return
    supporters.add(axiom)
    for pre in axiom.preconditions:
        supporting_axioms_helper(pre, axiom_from_eff, supporters)


def supporting_axioms(state, goals, axiom_instances):

    axiom_from_eff = axiom_achievers(axiom_instances, state)
    supporters = set()
    for goal in goals:
        if not isinstance(goal, Atom):

            continue
        if goal not in axiom_from_eff:
            return None
        supporting_axioms_helper(goal, axiom_from_eff, supporters)
    return supporters


def plan_supporting_axioms(evaluations, plan_instances, axiom_instances, goal):
    states = state_sequence(evaluations, plan_instances)
    for state, action in zip(states, plan_instances + [Goal(goal)]):
        yield supporting_axioms(state, action.preconditions, axiom_instances)


def apply_axioms(axiom_instances, state):
    for eval in axiom_achievers(axiom_instances, state):
        eval.assign(state)


def get_length(plan, evaluations):
    if plan is None:
        return INF
    return len(plan)


def get_cost(plan, evaluations):
    if plan is None:
        return INF
    plan_instances = [action.instantiate(args) for action, args in plan]
    return state_sequence(evaluations, plan_instances)[-1][TotalCost()]


def dump_evaluations(evaluations):
    eval_from_function = defaultdict(set)
    for eval in evaluations:
        eval_from_function[eval.head.function].add(eval)
    for i, fn in enumerate(sorted(eval_from_function, key=lambda fn: fn.name)):
        print i, len(eval_from_function[fn]), sorted(eval_from_function[fn], key=lambda eval: eval.head.args)
