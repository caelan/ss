from ss.model.functions import Predicate, Function, rename_functions, initialize, TotalCost, Increase
from ss.model.problem import Action, Axiom, Problem
from ss.model.streams import Stream
from ss.algorithms.incremental import incremental, exhaustive
from ss.algorithms.focused import focused

USE_NEGATIVE = False


def main(n=2):

    initial_poses = {'b{}'.format(i): i for i in xrange(n)}
    goal_poses = {'b0': 1}

    Block = Predicate('?b')
    Pose = Predicate('?p')
    Conf = Predicate('?q')

    Kin = Predicate('?q ?p', domain=[Conf('?q'), Pose('?p')])

    AtConf = Predicate('?q', domain=[Conf('?q')])
    AtPose = Predicate('?b ?p', domain=[Block('?b'), Pose('?p')])
    Holding = Predicate('?b', domain=[Block('?b')])
    HandEmpty = Predicate('')

    Safe = Predicate('?b ?p')
    Unsafe = Predicate('?b ?p')

    Collision = Predicate('?p1 ?p2', domain=[Pose('?p1'), Pose('?p2')],
                          fn=lambda p1, p2: p1 == p2, bound=False)
    CFree = Predicate('?p1 ?p2', domain=[Pose('?p1'), Pose('?p2')],
                      fn=lambda p1, p2: p1 != p2)

    Distance = Function('?q1 ?q2', domain=[Conf('?q1'), Conf('?q2')],
                        fn=lambda q1, q2: abs(q2 - q1) + 2, bound=2)

    rename_functions(locals())

    streams = [
        Stream(inp=[], domain=[],
               fn=lambda: ([(p,)] for p in xrange(n, n + 1)),
               out='?p', graph=[Pose('?p')]),
        Stream(inp='?p', domain=[Pose('?p')],
               fn=lambda p: iter([[(p,)]]),
               out='?q', graph=[Kin('?q', '?p')]),
    ]
    actions = [
        Action(name='Move', param='?q1 ?q2',
               pre=[AtConf('?q1'), Conf('?q1'), Conf('?q2')],
               eff=[AtConf('?q2'), ~AtConf('?q1'), Increase(TotalCost(), Distance('?q1', '?q2'))]),
        Action(name='Pick', param='?b ?p ?q',
               pre=[AtPose('?b', '?p'), HandEmpty(), AtConf(
                   '?q'), Block('?b'), Kin('?q', '?p')],
               eff=[Holding('?b'), ~AtPose('?b', '?p'), ~HandEmpty(), Increase(TotalCost(), 10)]),
    ]
    if USE_NEGATIVE:
        actions.append(Action(name='Place', param='?b ?p ?q',
                              pre=[Holding('?b'), AtConf('?q'),
                                   Block('?b'), Kin('?q', '?p')]
                              + [~Unsafe(b2, '?p') for b2 in initial_poses],
                              eff=[AtPose('?b', '?p'), HandEmpty(), ~Holding('?b')]))
    else:
        for b in initial_poses:
            actions += [
                Action(name='Place-' + b, param='?p ?q',
                       pre=[Holding(b), AtConf('?q'),
                            Block(b), Kin('?q', '?p')]
                       + [Safe(b2, '?p') for b2 in initial_poses if b2 != b],
                       eff=[AtPose(b, '?p'), HandEmpty(), ~Holding(b)])]

    axioms = [

        Axiom(param='?p1 ?b2 ?p2',
              pre=[AtPose('?b2', '?p2'), Block('?b2'), CFree('?p1', '?p2')],
              eff=Safe('?b2', '?p1')),
        Axiom(param='?p1 ?b2 ?p2',
              pre=[AtPose('?b2', '?p2'), Block('?b2'),
                   Collision('?p1', '?p2')],
              eff=Unsafe('?b2', '?p1')),
    ]
    initial_atoms = [

        HandEmpty(),
        AtConf(0),
        Pose(1),
        initialize(TotalCost(), 2),
    ] + [
        AtPose(b, p) for b, p in initial_poses.items()
    ] + [

    ]
    goal_literals = [AtPose(b, p) for b, p in goal_poses.items()]

    problem = Problem(initial_atoms, goal_literals, actions,
                      axioms, streams, objective=TotalCost())

    print problem
    print exhaustive(problem, verbose=True)


if __name__ == '__main__':
    main()
