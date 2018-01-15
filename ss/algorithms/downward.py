import math

from fast_downward import write,    TRANSLATE_OUTPUT, remove_paths, run_search
from ss.model.functions import Literal, TotalCost, Increase
from ss.utils import INF
from collections import defaultdict

COST_SCALE = 1
MAX_COST = (2**31 - 1) / 100


def transform_cost(cost):
    new_cost = int(math.ceil(COST_SCALE * cost))
    assert new_cost < MAX_COST
    return new_cost


def sas_version(version=3):
    return 'begin_version\n'           '%s\n'           'end_version\n' % version


def sas_action_costs(problem):
    return 'begin_metric\n'           '%s\n'           'end_metric\n' % int(problem.costs)


def sas_variables(problem):
    s = '%s\n' % len(problem.var_order)
    for i, var in enumerate(problem.var_order):
        axiom_layer = 0 if var in problem.derived_vars else -1
        n = len(problem.index_from_var_val[var])
        assert 2 <= n
        name = var if type(var) == str else 'var%s' % i
        s += 'begin_variable\n'             '%s\n'             '%s\n'             '%s\n' % (
            name, axiom_layer, n)
        for j in xrange(n):

            s += '%s-%s\n' % (i, j)
        s += 'end_variable\n'
    return s


def sas_mutexes(problem):
    s = '%s\n' % len(problem.mutexes)
    for mutex in problem.mutexes:
        s += 'begin_mutex_group\n'             '%s\n' % len(mutex)
        for var, val in mutex:
            s += '%s %s\n' % (var, val)
        s += 'end_mutex_group'
    return s


def sas_initial(problem):

    s = 'begin_state\n'
    for var in problem.var_order:
        val = problem.get_val(var, problem.initial[var])
        s += '%s\n' % val
    s += 'end_state\n'
    return s


def sas_goal(problem):
    s = 'begin_goal\n'        '%s\n' % len(problem.goal)
    for atom in problem.goal:
        s += '%s %s\n' % problem.get_var_val(atom)
    s += 'end_goal\n'
    return s


def sas_actions(problem):
    s = '%s\n' % len(problem.actions)
    for i, action in enumerate(problem.actions):
        effects = filter(lambda a: isinstance(a, Literal)
                         and problem.has_var_val(a), action.effects)
        assert effects
        s += 'begin_operator\n'             'a-%s\n'             '%s\n' % (
            i, len(action.preconditions))
        for atom in action.preconditions:
            s += '%s %s\n' % problem.get_var_val(atom)
        s += '%s\n' % len(effects)
        for atom in effects:
            s += '0 %s -1 %s\n' % problem.get_var_val(atom)
        cost = 0
        for incr in filter(lambda a: isinstance(a, Increase), action.effects):
            assert incr.head == TotalCost()
            cost += incr.value
        s += '%s\n'             'end_operator\n' % transform_cost(cost)
    return s


def sas_axioms(problem):
    s = '%s\n' % len(problem.axioms)
    for axiom in problem.axioms:
        s += 'begin_rule\n'
        s += '%s\n' % len(axiom.preconditions)
        for atom in axiom.preconditions:
            s += '%s %s\n' % problem.get_var_val(atom)
        s += '%s -1 %s\n' % problem.get_var_val(axiom.effect)
        s += 'end_rule\n'
    return s


def to_sas(problem):
    return sas_version() + sas_action_costs(problem) + sas_variables(problem) + sas_mutexes(problem) + sas_initial(problem) + sas_goal(problem) + sas_actions(problem) + sas_axioms(problem)


class DownwardProblem(object):
    costs = True

    def __init__(self, initial, goal, actions, axioms):
        self.goal = goal
        self.actions = []
        self.axioms = []

        self.index_from_var = {}
        self.var_order = []
        self.index_from_var_val = {}
        self.val_order_from_var = {}
        self.mutexes = []
        self.derived_vars = set()

        for atom in goal:
            if isinstance(atom, Literal):
                self._add_val(atom.head, False)
                self._add_val(atom.head, True)

        for op in (actions + axioms):

            for atom in op.preconditions:
                if isinstance(atom, Literal):
                    self._add_val(atom.head, False)
                    self._add_val(atom.head, True)

        for op in actions:
            if any(isinstance(a, Literal) and self.has_var_val(a) for a in op.effects):
                self.actions.append(op)
        for op in axioms:
            if self.has_var_val(op.effect):
                self.axioms.append(op)
                self.derived_vars.add(op.effect.head)

        self.initial = defaultdict(bool)
        for atom in initial:
            var = atom.head
            val = atom.value
            if isinstance(atom, Literal) and (var in self.index_from_var):
                self.initial[var] = val

    def _add_var(self, var):
        if var not in self.index_from_var:
            self.index_from_var[var] = len(self.index_from_var)
            self.var_order.append(var)
            self.index_from_var_val[var] = {}
            self.val_order_from_var[var] = []

    def _add_val(self, var, val):
        self._add_var(var)
        if val not in self.index_from_var_val[var]:
            self.index_from_var_val[var][val] = len(
                self.index_from_var_val[var])
            self.val_order_from_var[var].append(val)

    def get_var(self, var):
        return self.index_from_var[var]

    def get_val(self, var, val):
        return self.index_from_var_val[var][val]

    def has_var_val(self, atom):
        var, val = atom.head, atom.value
        return (var in self.index_from_var) and (val in self.index_from_var_val[var])

    def get_var_val(self, atom):
        var, val = atom.head, atom.value
        return self.get_var(var), self.get_val(var, val)

    def __repr__(self):
        return '{}\n'               'Variables: {}\n'               'Actions: {}\n'               'Axioms: {}\n'               'Goals: {}'.format(self.__class__.__name__,
                                                                                                                                                  len(
                                                                                                                                                      self.var_order),
                                                                                                                                                  len(
                                                                                                                                                      self.actions),
                                                                                                                                                  len(
                                                                                                                                                      self.axioms),
                                                                                                                                                  len(self.goal))


def convert_solution(solution, problem):

    plan = []
    for line in solution.split('\n')[:-2]:
        index = int(line.strip('( )')[2:])
        plan.append(problem.actions[index])

    return plan


def solve_sas(problem, planner='max-astar', max_time=INF, max_cost=INF, verbose=False, clean=True):

    remove_paths()
    write(TRANSLATE_OUTPUT, to_sas(problem))
    plan = run_search(planner, max_time, max_cost, verbose)
    if clean:
        remove_paths()
    if plan is None:
        return None
    return convert_solution(plan, problem)
