Serialization
====================================

As a secondary feature aimed at enabling the use of :func:`dcargs.cli` for general
configuration use cases, we also introduce functions for human-readable
dataclass serialization:

- :func:`dcargs.to_yaml` and :func:`dcargs.from_yaml` convert between YAML-style
  strings and dataclass instances.

The functions attempt to strike a balance between flexibility and robustness —
in contrast to naively dumping or loading dataclass instances (via pickle,
PyYAML, etc), explicit type references enable custom tags that are robust
against code reorganization and refactor, while a PyYAML backend enables
serialization of arbitrary Python objects.

Note that we generally prefer to use YAML purely for serialization, as opposed
to a configuration interface that humans are expected to manually write or
modify. Specifying things like loadable base configurations can be done directly
in Python, which enables all of the usual autocompletion and type checking
features.

