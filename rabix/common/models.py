import six

from uuid import uuid4

from rabix.common.errors import ValidationError


class App(object):

    def __init__(self, app_id, inputs, outputs, app_description=None,
                 annotations=None, platform_features=None):
        self.id = app_id
        self.inputs = inputs
        self.outputs = outputs
        self.app_description = app_description
        self.annotations = annotations
        self.platform_features = platform_features
        self._inputs = {io.id: io for io in inputs}
        self._outputs = {io.id: io for io in outputs}

    def install(self):
        pass

    def run(self, job):
        raise NotImplementedError("Method 'run' is not implemented"
                                  " in the App class")

    def get_input(self, name):
        return self._inputs.get(name)

    def get_output(self, name):
        return self._outputs.get(name)

    def validate_inputs(self, input_values):
        for inp in self.inputs:
            if inp.id in input_values:
                if not inp.validate(input_values[inp.id]):
                    return False
            elif inp.required:
                return False
        return True

    def to_dict(self):
        return {
            '@id': self.id,
            'inputs': [inp.to_dict() for inp in self.inputs],
            'outputs': [outp.to_dict() for outp in self.outputs],
            'appDescription': self.app_description,
            'annotations': self.annotations,
            'platformFeatures': self.platform_features
        }


class IO(object):

    def __init__(self, port_id, depth=0, validator=None, required=False,
                 annotations=None):
        self.id = port_id
        self.depth = depth
        self.validator = validator
        self.required = required
        self.annotations = annotations

    def validate(self, value):
        return self.validator.validate(value)

    def to_dict(self):
        return {
            '@id': self.id,
            '@type': 'IO',
            'depth': self.depth,
            'schema': self.validator.schema,
            'required': self.required,
            'annotations': self.annotations
        }

    @classmethod
    def from_dict(cls, context, d):
        return cls(d.get('@id', str(uuid4())),
                   depth=d.get('depth'),
                   validator=context.from_dict(d.get('schema')),
                   required=d['required'],
                   annotations=d['annotations'])


class Job(object):

    def __init__(self, job_id, app, inputs):
        # if not app.validate_inputs(inputs):
        #     raise ValidationError("Invalid inputs for application %s" % app.id)
        self.id = job_id
        self.app = app
        self.inputs = inputs

    def run(self):
        return self.app.run(self)

    def to_dict(self):
        return {
            '@id': self.id,
            '@type': 'Job',
            'app': self.app.to_dict(),
            'inputs': self.inputs
        }

    def __str__(self):
        return str(self.to_dict())

    __repr__ = __str__

    @classmethod
    def from_dict(cls, context, d):
        return cls(
            d.get('@id', str(uuid4())), context.from_dict(d['app']), d['inputs']
        )

# def from_dict(d):
#     if d is None:
#         return None
#     if isinstance(d, list):
#         return [from_dict(e) for e in d]
#     if not isinstance(d, dict):
#         return d
#     if not '@type' in d:
#         return {k: from_dict(v) for k, v in six.iteritems(d)}
#     type_name = d['@type']
#     typ = TYPE_MAP.get(type_name)
#     if not typ:
#         raise ValidationError("Unknown type: %s" % type_name)
#     return typ.from_dict(d)
