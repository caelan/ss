import cProfile
import pstats
from itertools import product

from ss.model.problem import Action, Axiom, Problem
from ss.model.streams import FnStream, ListStream

from ss.algorithms.plan_focused import plan_focused
from ss.model.functions import Predicate, Function, rename_functions, initialize, TotalCost, Increase


class Pose(object):

    def __init__(self, o, x):
        self.o = o
        self.x = x

    def __repr__(self):
        return 'P({})'.format(self.x)


class Grasp(object):

    def __init__(self, o):
        self.o = o

    def __repr__(self):
        return 'G()'


class BConf(object):

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return 'BQ({},{})'.format(self.x, self.y)


A = '?a'
BQ = '?q'
BQ2 = '?q2'
O = '?o'
O2 = '?o2'
P = '?p'
P2 = '?p2'
G = '?g'
C = '?c'
V = '?v'

POSE = Predicate([P])
BCONF = Predicate([BQ])

IsPose = Predicate([O, P])
IsGrasp = Predicate([O, G])
IsMovable = Predicate([O])

IsKin = Predicate([A, O, P, G, BQ])
IsSupported = Predicate([P, P2])
IsVisible = Predicate([P, BQ])

IsArm = Predicate([A])
IsClass = Predicate([O, C])

AtPose = Predicate([O, P])
AtBConf = Predicate([BQ])

HasGrasp = Predicate([A, O, G])
HandEmpty = Predicate([A])

Holding = Predicate([A, O])
On = Predicate([O, O2])
Nearby = Predicate([O])

Located = Predicate([O])
Scanned = Predicate([O])
Stackable = Predicate([O, O2])

Open = Predicate([A])

Known = Predicate([V])
Computable = Predicate([V])
HasPos = Predicate([P])
HasOri = Predicate([P])

rename_functions(locals())


def get_abstract_problem():

    actions = [
        Action(name='abs_pick', param=[A, O, O2],
               pre=[IsArm(A), Stackable(O, O2),
                    HandEmpty(A), Scanned(O), Open(A)],
               eff=[Holding(A, O), ~HandEmpty(A)]),

        Action(name='abs_pick', param=[A, O, O2],
               pre=[IsArm(A), Stackable(O, O2),
                    Holding(A, O), Scanned(O2)],
               eff=[HandEmpty(A), Open(A), ~Holding(A, O)]),

        Action(name='abs_move', param=[O, O2],
               pre=[Nearby(O)],
               eff=[Nearby(O2), ~Nearby(O),
                    Increase(TotalCost(), MoveCost(O, O2))] +
               [~Scanned(o) for o in movable_names]),

        Action(name='abs_open', param=[A],
               pre=[HandEmpty(A)],
               eff=[Open(A)]),



        Action(name='abs_scan', param=[O],
               pre=[Located(O)],
               eff=[Scanned(O)]),

        Action(name='abs_observe', param=[O, O2],
               pre=[Stackable(O, O2),
                    Scanned(O2), ~Located(O)],
               eff=[Located(O),
                    Increase(TotalCost(), ScanCost(O, O2))]),
    ]
    axioms = []


def get_problem():
    initial_bq = BConf(0, 1)

    arms = ['l']

    initial_movable = {'b': [3, 9]}
    initial_surface = {'t': [3, 6, 9]}

    initial_room = {'f': [0]}

    pose_from_name = {}
    class_from_name = {}
    for initial in [initial_movable, initial_surface, initial_room]:
        for cl in initial:
            for i, x in enumerate(initial[cl]):
                name = cl + str(i)
                class_from_name[name] = cl
                pose_from_name[name] = Pose(name, x)
    movable_names = {n for n, cl in class_from_name.items()
                     if cl in initial_movable}
    surface_names = {n for n, cl in class_from_name.items()
                     if cl in initial_surface}
    room_names = {n for n, cl in class_from_name.items() if cl in initial_room}

    assert len(room_names) == 1
    room = list(room_names)[0]

    located = dict([(room, None)] + [(n, room) for n in surface_names])
    scanned = {room}

    print pose_from_name
    print class_from_name
    print movable_names, surface_names, room_names

    base_constant_cost = 1

    DistanceCost = Function([BQ, BQ2], domain=[BCONF(BQ), BCONF(BQ2)],
                            fn=lambda q1, q2: abs(
                                q2.x - q1.x) + abs(q2.y - q1.y) + base_constant_cost,
                            bound=base_constant_cost)

    scan_constant_cost = 1

    ScanCost = Function([O, O2], domain=[Stackable(O, O2)],
                        fn=lambda o, o2: scan_constant_cost,
                        bound=scan_constant_cost)

    def is_visible(p, bq):
        if p.o in room_names:
            return True
        elif p.o in surface_names:
            return (p.x == bq.x) and (abs(bq.y) <= 2)
        elif p.o in movable_names:
            return (p.x == bq.x) and (abs(bq.y) <= 2)
        else:
            raise ValueError(p.o)

    IsVisible = Predicate([P, BQ], domain=[POSE(
        P), BCONF(BQ)], fn=is_visible, bound=None)

    bound = 'shared'

    streams = [
        FnStream(name='grasp', inp=[O], domain=[IsMovable(O)],
                 fn=lambda o: (Grasp(o),),
                 out=[G], graph=[IsGrasp(O, G)], bound=bound),

        ListStream(name='ik', inp=[A, O, P, G], domain=[IsArm(A), IsPose(O, P), IsGrasp(O, G)],
                   fn=lambda r, o, p, g: [
                       (BConf(p.x, +1) if r == 'r' else BConf(p.x, -1),)],
                   out=[BQ], graph=[IsKin(A, O, P, G, BQ), IsVisible(P, BQ), BCONF(BQ)], bound=bound),

        FnStream(name='support', inp=[O, O2, P2],
                 domain=[IsMovable(O), Stackable(O, O2), IsPose(O2, P2)],
                 fn=lambda o, o2, p: (Pose(o, p.x),),
                 out=[P], graph=[IsPose(O, P), IsSupported(P, P2), POSE(P), HasPos(P), HasOri(P)], bound=bound),
    ]

    def sample_visible_base(o, p):
        if p.o in room_names:
            return []
        elif p.o in surface_names:
            return [(BConf(p.x, +2),)]
        elif p.o in movable_names:

            return [(BConf(p.x, +2),)]
        else:
            raise ValueError(p.o)

    VisibleStream = Predicate([O, P, BQ])
    streams.append(ListStream(name='vis', inp=[O, P], domain=[IsPose(O, P)], fn=sample_visible_base,
                              out=[BQ], graph=[IsVisible(P, BQ), BCONF(BQ), VisibleStream(O, P, BQ)], bound=bound))

    rename_functions(locals())

    actions = [
        Action(name='pick', param=[A, O, P, G, BQ],
               pre=[IsKin(A, O, P, G, BQ),
                    HandEmpty(A), AtPose(O, P), AtBConf(BQ), Scanned(O), Open(A)],
               eff=[HasGrasp(A, O, G), ~HandEmpty(A), ~AtPose(O, P), ~Open(A),
                    Increase(TotalCost(), 1)]),

        Action(name='place', param=[A, O, P, G, BQ, O2, P2],
               pre=[IsKin(A, O, P, G, BQ), IsPose(O2, P2), IsSupported(P, P2),
                    HasGrasp(A, O, G), AtBConf(BQ), AtPose(O2, P2), Scanned(O2)],
               eff=[HandEmpty(A), AtPose(O, P), Open(A), ~HasGrasp(A, O, G),
                    Increase(TotalCost(), 1)]),

        Action(name='move_base', param=[BQ, BQ2],
               pre=[BCONF(BQ), BCONF(BQ2),
                    AtBConf(BQ), Computable(BQ2)],
               eff=[AtBConf(BQ2), ~AtBConf(BQ),

                    Increase(TotalCost(), base_constant_cost)] +
               [~Scanned(o) for o in movable_names]),


        Action(name='open', param=[A],
               pre=[HandEmpty(A)],
               eff=[Open(A)]),

        Action(name='scan', param=[O, P, BQ],
               pre=[IsPose(O, P), IsVisible(P, BQ),
                    AtPose(O, P), AtBConf(BQ), Located(O)],
               eff=[Scanned(O), HasOri(P)]),

        Action(name='observe', param=[O, P, O2, P2],
               pre=[IsPose(O, P), IsPose(O2, P2), Stackable(O, O2),
                    AtPose(O, P), Scanned(O2), ~Located(O)],
               eff=[Located(O), IsSupported(P, P2), HasPos(P),
                    Increase(TotalCost(), ScanCost(O, O2))]),


    ]
    axioms = [
        Axiom(param=[A, O, G],
              pre=[IsArm(A), IsGrasp(O, G),
                   HasGrasp(A, O, G)],
              eff=Holding(A, O)),

        Axiom(param=[O, P, O2, P2],
              pre=[IsPose(O, P), IsPose(O2, P2), IsSupported(P, P2),
                   AtPose(O, P), AtPose(O2, P2)],
              eff=On(O, O2)),



        Axiom(param=[V],
              pre=[Known(V)],
              eff=Computable(V)),
        Axiom(param=[O, P, V],
              pre=[VisibleStream(O, P, V), HasPos(P)],
              eff=Computable(V)),
        Axiom(param=[A, O, P, G, V],
              pre=[IsKin(A, O, P, G, V), HasOri(P)],
              eff=Computable(V)),
    ]

    initial_atoms = [
        BCONF(initial_bq), AtBConf(initial_bq), Known(initial_bq),
        initialize(TotalCost(), 0),
    ]
    for arm in arms:
        initial_atoms += [IsArm(arm), Open(arm), HandEmpty(arm)]
    for n, p in pose_from_name.items():
        initial_atoms += [IsPose(n, p), AtPose(n, p), POSE(p)]

    initial_atoms += map(IsMovable, movable_names)
    initial_atoms += [Stackable(*pair) for pair in
                      list(product(movable_names, surface_names)) + list(product(surface_names, room_names))]
    for n, cl in class_from_name.items():
        initial_atoms.append(IsClass(n, cl))

    for o, o2 in located.items():
        initial_atoms += [Located(o), HasPos(pose_from_name[o])]
        if o2 is not None:
            initial_atoms += [IsSupported(pose_from_name[o],
                                          pose_from_name[o2])]
    for o in scanned:
        initial_atoms += [Scanned(o), HasOri(pose_from_name[o])]

    goal_literals = [Holding('l', 'b0')]

    return Problem(initial_atoms, goal_literals, actions, axioms, streams, objective=TotalCost())


def main(verbose=True):
    problem = get_problem()
    print problem
    problem.dump()

    pr = cProfile.Profile()
    pr.enable()

    plan = plan_focused(problem, verbose=verbose)

    pr.disable()
    pstats.Stats(pr).sort_stats('tottime').print_stats(10)

    if plan is None:
        print plan
        return
    print 'Length', len(plan)
    for i, act in enumerate(plan):
        print i, act

if __name__ == '__main__':
    main()
