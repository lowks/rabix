import six
import logging

from collections import defaultdict

from rabix.workflows.workflow_app import \
    InputRelation, Relation, OutputRelation
from rabix.common.errors import RabixError
from rabix.common.models import IO

log = logging.getLogger(__name__)


class PartialJob(object):

    def __init__(self, node_id, app, input_connections, input_counts, outputs):
        self.result = None
        self.status = 'WAITING'
        self.node_id = node_id
        self.tool = app
        self.job = {'inputs': input_connections}
        self.input_counts = input_counts
        self.outputs = outputs

        self.running = []
        self.resources = None

    @property
    def resolved(self):
        for name, cnt in six.iteritems(self.input_counts):
            if cnt > 0:
                return False
        return True

    def resolve_input(self, input_port, results):
        log.debug("Resolving input '%s' with value %s" % (input_port, results))
        input_count = self.input_counts[input_port]
        if input_count <= 0:
            raise RabixError("Input already satisfied")
        self.input_counts[input_port] = input_count - 1
        # recursive_merge(self.job['inputs'].get(input_port), results)
        prev_result = self.job['inputs'].get(input_port)
        if prev_result is None:
            self.job['inputs'][input_port] = results
        elif isinstance(prev_result, list):
            prev_result.append(results)
        else:
            self.job['inputs'][input_port] = [prev_result, results]
        return self.resolved

    def propagate_result(self, result):
        log.debug("Propagating result: %s" % result)
        self.result = result
        for k, v in six.iteritems(result):
            log.debug("Propagating result: %s, %s" % (k, v))
            self.outputs[k].resolve_input(v)


class ExecRelation(object):

    def __init__(self, node, input_port):
        self.node = node
        self.input_port = input_port

    def resolve_input(self, result):
        self.node.resolve_input(self.input_port, result)


class OutRelation(object):

    def __init__(self, graph, name):
        self.name = name
        self.graph = graph

    def resolve_input(self, result):
        self.graph.outputs[self.name] = result


class ExecutionGraph(object):

    def __init__(self, workflow, job):
        self.workflow = workflow
        self.executables = {}
        self.ready = {}
        self.job = job
        self.outputs = {}

        graph = workflow.graph

        for node_id in graph.back_topo_sort()[1]:
            executable = self.make_executable(node_id)
            if executable:
                self.executables[node_id] = executable

        workflow.hide_nodes(IO)

        self.order = graph.back_topo_sort()[1]

    def make_executable(self, node_id):
        node = self.graph.node_data(node_id)
        if isinstance(node, IO):
            return None

        out_edges = self.graph.out_edges(node_id)
        in_edges = self.graph.inc_edges(node_id)

        outputs = {}
        input_counts = ExecutionGraph.count_inputs(self.graph, in_edges)
        for out_edge in out_edges:
            rel = self.graph.edge_data(out_edge)
            if isinstance(rel, Relation):
                tail = self.executables[self.graph.tail(out_edge)]
                outputs[rel.src_port] = ExecRelation(tail, rel.dst_port)
            elif isinstance(rel, OutputRelation):
                tail = self.graph.tail(out_edge)
                outputs[rel.src_port] = OutRelation(self, tail)

        executable = PartialJob(
            node_id, node.app, node.inputs, input_counts, outputs
        )

        for in_edge in in_edges:
            rel = self.graph.edge_data(in_edge)
            head = self.graph.head(in_edge)
            if (isinstance(rel, InputRelation) and
                    head in self.job['inputs']):

                executable.resolve_input(
                    rel.dst_port, self.job['inputs'][head]
                )

        return executable

    @staticmethod
    def count_inputs(graph, in_edges):
        input_counts = defaultdict(lambda: 0)
        for edge in in_edges:
            relation = graph.edge_data(edge)
            input_count = input_counts[relation.dst_port]
            input_counts[relation.dst_port] = input_count + 1
        return input_counts

    def job_done(self, node_id, results):
        ex = self.executables[node_id]
        ex.propagate_result(results)

    def next_job(self):
        if not self.order:
            return None
        return self.executables[self.order.pop()]

    def has_next(self):
        return len(self.order) > 0

    @property
    def graph(self):
        return self.workflow.graph


# Smoke test
if __name__ == '__main__':
    from os.path import abspath, join
    from rabix.common.ref_resolver import from_url
    from rabix.workflows.workflow_app import WorkflowApp

    def root_relative(path):
        return abspath(join(__file__, '../../../', path))

    doc = from_url(root_relative('examples/workflow.yml'))

    wf = WorkflowApp(doc['workflows']['add_one_mul_two']['steps'])
    job = doc['jobs']['batch_add_one_mul_two']

    eg = ExecutionGraph(wf, job)
