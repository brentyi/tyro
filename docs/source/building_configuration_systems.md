# Building configuration systems

Beyond building simple command-line interfaces, :func:`tyro.cli()` is designed
to scale to larger configuration systems such as those typically built with
libraries like [`hydra`](https://github.com/facebookresearch/hydra).

For a live example of this, see
[nerfstudio](https://github.com/nerfstudio-project/nerfstudio/). Notably,
`nerfstudio`'s configuration system is implemented entirely in Python, no YAML
needed, and has full tab completion support in your terminal.

For overriding a dynamically loaded configuration object (typically a
dataclass), the `default=` parameter of :func:`tyro.cli()` can be used. If you
have multiple default configuration objects and need to select one to pass in as
a default -- this might be a YAML file or config instance -- an environment
variable or manually parsed (via `sys.argv`) positional argument can be used.

For exposing each of these base configurations as subcommands, see our
[base config example](./examples/10_base_configs).
