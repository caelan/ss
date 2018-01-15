from ss.utils import Hashable, INF


class OutputSet(Hashable):

    def __init__(self, stream, inputs, index):
        self.stream = stream
        self.inputs = tuple(inputs)
        self.index = index
        super(OutputSet, self).__init__(stream, inputs, index)

    def get_instance(self):
        return self.stream.get_instance(self.inputs)

    def __repr__(self):
        param = self.stream.outputs[self.index]

        return '%s-%s' % (param, id(self) % 100)


class SharedOutputSet(Hashable):

    def __init__(self, stream, index):
        self.stream = stream
        self.index = index
        super(SharedOutputSet, self).__init__(stream, index)

    def __repr__(self):
        return '%s-%s' % (self.stream.outputs[self.index], self.stream.name)


class Bound(object):
    pass


class GenericBound(Bound):

    def __init__(self, relation, inputs, parameter):
        self.relation = relation
        self.inputs = inputs
        self.parameter = parameter


class Interval(Bound):

    def __init__(self, minimum, maximum):
        assert minimum <= maximum
        self.minimum = minimum
        self.maximum = maximum


class Finite(Bound):

    def __init__(self, values):
        self.values = values


class Singleton(Bound):

    def __init__(self, value):
        self.value = value

zero_to_inf = Interval(0, INF)
neg_inf_to_inf = Interval(-INF, INF)
