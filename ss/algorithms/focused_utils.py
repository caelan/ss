from ss.algorithms.universe import Universe
from ss.utils import INF


def evaluate_stream_instances(queue, evaluations, max_evals):
    num_evals = 0
    while queue and (num_evals < max_evals):
        num_evals += 1
        instance = queue.popleft()
        if not instance.enumerated:
            evaluations.update(instance.next_atoms())
        if not instance.enumerated:
            queue.append(instance)


def evaluate_eager(problem, evaluations):
    eager_universe = Universe(problem, evaluations,
                              use_bounds=False, only_eager=True)
    evaluate_stream_instances(
        eager_universe.stream_queue, eager_universe.evaluations, INF)

    return eager_universe.evaluations


def isolated_reset_fn(disabled, evaluations):

    evaluate_stream_instances(disabled, evaluations, len(disabled))


def revisit_reset_fn(disabled, evaluations):
    while disabled:
        instance = disabled.popleft()
        instance.disabled = False
