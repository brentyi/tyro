# mypy: ignore-errors
"""Tests for ml_collections integration."""

import dataclasses

from helptext_utils import get_helptext_with_checks

import tyro


def test_basic_configdict() -> None:
    """Test basic ConfigDict parsing."""
    from ml_collections import ConfigDict

    def get_config() -> ConfigDict:
        config = ConfigDict()
        config.wandb = ConfigDict()
        config.wandb.mode = "online"
        config.wandb.project = "test-project"

        config.network = ConfigDict()
        config.network.policy_layer_dims = (128,) * 3
        config.network.value_layer_dims = (256,) * 5
        return config

    def train(config: ConfigDict = get_config()) -> ConfigDict:
        return config  # type: ignore

    # Test parsing with CLI arguments
    result = tyro.cli(
        train,
        args=[
            "--config.wandb.mode=offline",
            "--config.network.policy-layer-dims=64",
        ],
    )
    assert result.wandb.mode == "offline"  # type: ignore
    assert result.wandb.project == "test-project"  # type: ignore
    assert result.network.policy_layer_dims == (64,)  # type: ignore
    assert result.network.value_layer_dims == (256, 256, 256, 256, 256)  # type: ignore

    # Test helptext
    helptext = get_helptext_with_checks(train)
    assert "--config.wandb.mode" in helptext
    assert "--config.wandb.project" in helptext
    assert "--config.network.policy-layer-dims" in helptext
    assert "--config.network.value-layer-dims" in helptext


def test_field_references() -> None:
    """Test ConfigDict with FieldReference."""
    from ml_collections import ConfigDict, FieldReference

    def get_config() -> ConfigDict:
        config = ConfigDict()
        layer_dim_ref = FieldReference((128,) * 3)
        config.layer_dims = layer_dim_ref

        config.network = ConfigDict()
        config.network.policy_layer_dims = layer_dim_ref
        config.network.value_layer_dims = layer_dim_ref
        return config

    def train(config: ConfigDict = get_config()) -> None:
        return config  # type: ignore

    # Test updating field reference via CLI
    result = tyro.cli(
        train,
        args=[
            "--config.layer-dims=64",
        ],
    )
    assert result.layer_dims == (64,)  # type: ignore
    # Field references also update, so these values should be the same as layer_dims
    assert result.network.policy_layer_dims == (64,)  # type: ignore
    assert result.network.value_layer_dims == (64,)  # type: ignore

    # Test updating directly instead of through reference
    # In this case, updating policy_layer_dims directly updates the reference too
    result = tyro.cli(
        train,
        args=[
            "--config.network.policy-layer-dims=32",
        ],
    )
    # When we update one of the references, the original gets updated too
    assert result.layer_dims == (32,)  # type: ignore
    assert result.network.policy_layer_dims == (32,)  # type: ignore
    assert result.network.value_layer_dims == (32,)  # type: ignore

    # Test helptext
    helptext = get_helptext_with_checks(train)
    assert "--config.layer-dims" in helptext
    assert "Reference default: (128, 128, 128)" in helptext
    assert "(assigns reference)" in helptext


def test_nested_configdict() -> None:
    """Test deeply nested ConfigDict objects."""
    from ml_collections import ConfigDict

    def get_config() -> ConfigDict:
        config = ConfigDict()
        config.level1 = ConfigDict()
        config.level1.level2 = ConfigDict()
        config.level1.level2.level3 = ConfigDict()
        config.level1.level2.level3.value = 42
        config.level1.level2.level3.sequence = ["a", "b", "c"]  # type: ignore
        return config

    def nested_fn(config: ConfigDict = get_config()) -> ConfigDict:
        return config

    # Test updating deeply nested values
    result = tyro.cli(
        nested_fn,
        args=[
            "--config.level1.level2.level3.value=100",
            "--config.level1.level2.level3.sequence=x",
        ],
    )
    assert result.level1.level2.level3.value == 100  # type: ignore

    # Since sequence is a method on ConfigDict, we need to access it differently
    sequence_value = result.level1.level2.level3["sequence"]  # type: ignore
    assert isinstance(sequence_value, list)
    assert len(sequence_value) == 1
    assert sequence_value[0] == "x"

    # Test helptext
    helptext = get_helptext_with_checks(nested_fn)
    assert "--config.level1.level2.level3.value" in helptext
    assert "--config.level1.level2.level3.sequence" in helptext


def test_configdict_in_dataclass() -> None:
    """Test ConfigDict as a field within a dataclass."""
    from ml_collections import ConfigDict

    def get_config() -> ConfigDict:
        config = ConfigDict()
        config.policy_layer_dims = (128,) * 3
        config.value_layer_dims = (256,) * 2
        return config

    @dataclasses.dataclass
    class TrainingConfig:
        learning_rate: float = 0.001
        batch_size: int = 64
        network: ConfigDict = dataclasses.field(default_factory=get_config)

    # Create a test function that uses the dataclass with a configdict
    def train_with_config(config: ConfigDict = get_config()) -> ConfigDict:
        return config

    # Test with pure ConfigDict
    result = tyro.cli(
        train_with_config,
        args=[
            "--config.policy-layer-dims=64",
        ],
    )
    assert result.policy_layer_dims == (64,)
    assert result.value_layer_dims == (256, 256)

    # Test helptext
    helptext = get_helptext_with_checks(train_with_config)
    assert "--config.policy-layer-dims" in helptext
    assert "--config.value-layer-dims" in helptext


def test_configdict_with_tuples() -> None:
    """Test ConfigDict with tuple fields of different types."""
    from ml_collections import ConfigDict

    def get_config() -> ConfigDict:
        config = ConfigDict()
        config.int_tuple = (1, 2, 3)
        config.float_tuple = (1.0, 2.0, 3.0)
        config.str_tuple = ("a", "b", "c")
        config.mixed_tuple = (1, "a", 2.0)
        return config

    def process(config: ConfigDict = get_config()) -> ConfigDict:
        return config

    # Test various tuple types
    result = tyro.cli(
        process,
        args=[
            "--config.int-tuple=10",
            "--config.float-tuple=1.5",
            "--config.str-tuple=x",
            "--config.mixed-tuple",
            "5",
            "3",
            "1",
        ],
    )
    assert result.int_tuple == (10,)
    assert result.float_tuple == (1.5,)
    assert result.str_tuple == ("x",)
    assert result.mixed_tuple == (5, "3", 1.0)

    # Test helptext
    helptext = get_helptext_with_checks(process)
    assert "--config.int-tuple" in helptext
    assert "--config.float-tuple" in helptext
    assert "--config.str-tuple" in helptext


# FrozenConfigDict Tests


def test_basic_frozenconfigdict() -> None:
    """Test basic FrozenConfigDict parsing."""
    from ml_collections import FrozenConfigDict

    def get_config() -> FrozenConfigDict:
        config_dict = {}
        config_dict["wandb"] = {}
        config_dict["wandb"]["mode"] = "online"
        config_dict["wandb"]["project"] = "test-project"

        config_dict["network"] = {}
        config_dict["network"]["policy_layer_dims"] = (128,) * 3
        config_dict["network"]["value_layer_dims"] = (256,) * 5
        return FrozenConfigDict(config_dict)

    def train(config: FrozenConfigDict = get_config()) -> FrozenConfigDict:
        return config  # type: ignore

    # Test parsing with CLI arguments
    result = tyro.cli(
        train,
        args=[
            "--config.wandb.mode=offline",
            "--config.network.policy-layer-dims=64",
        ],
    )
    assert result.wandb.mode == "offline"  # type: ignore
    assert result.wandb.project == "test-project"  # type: ignore
    assert result.network.policy_layer_dims == (64,)  # type: ignore
    assert result.network.value_layer_dims == (256, 256, 256, 256, 256)  # type: ignore

    # Test helptext
    helptext = get_helptext_with_checks(train)
    assert "--config.wandb.mode" in helptext
    assert "--config.wandb.project" in helptext
    assert "--config.network.policy-layer-dims" in helptext
    assert "--config.network.value-layer-dims" in helptext


def test_field_references_frozenconfigdict() -> None:
    """Test FrozenConfigDict with FieldReference."""
    from ml_collections import FieldReference, FrozenConfigDict

    def get_config() -> FrozenConfigDict:
        config_dict = {}
        layer_dim_ref = FieldReference((128,) * 3)
        config_dict["layer_dims"] = layer_dim_ref

        config_dict["network"] = {}
        config_dict["network"]["policy_layer_dims"] = layer_dim_ref
        config_dict["network"]["value_layer_dims"] = layer_dim_ref
        return FrozenConfigDict(config_dict)

    def train(config: FrozenConfigDict = get_config()) -> None:
        return config  # type: ignore

    # Test updating field reference via CLI
    result = tyro.cli(
        train,
        args=[
            "--config.layer-dims=64",
        ],
    )
    assert result.layer_dims == (64,)  # type: ignore
    # Field references also update, so these values should be the same as layer_dims
    assert result.network.policy_layer_dims == (64,)  # type: ignore
    assert result.network.value_layer_dims == (64,)  # type: ignore

    # Test updating directly instead of through reference
    # In this case, updating policy_layer_dims directly updates the reference too
    result = tyro.cli(
        train,
        args=[
            "--config.network.policy-layer-dims=32",
        ],
    )
    # When we update one of the references, the original gets updated too
    assert result.layer_dims == (32,)  # type: ignore
    assert result.network.policy_layer_dims == (32,)  # type: ignore
    assert result.network.value_layer_dims == (32,)  # type: ignore

    # Test helptext
    helptext = get_helptext_with_checks(train)
    assert "--config.layer-dims" in helptext
    assert "Reference default: (128, 128, 128)" in helptext
    assert "(assigns reference)" in helptext


def test_nested_frozenconfigdict() -> None:
    """Test deeply nested FrozenConfigDict objects."""
    from ml_collections import FrozenConfigDict

    def get_config() -> FrozenConfigDict:
        config_dict = {}
        config_dict["level1"] = {}
        config_dict["level1"]["level2"] = {}
        config_dict["level1"]["level2"]["level3"] = {}
        config_dict["level1"]["level2"]["level3"]["value"] = 42
        config_dict["level1"]["level2"]["level3"]["sequence"] = ["a", "b", "c"]
        return FrozenConfigDict(config_dict)

    def nested_fn(config: FrozenConfigDict = get_config()) -> FrozenConfigDict:
        return config

    # Test updating deeply nested values
    result = tyro.cli(
        nested_fn,
        args=[
            "--config.level1.level2.level3.value=100",
            "--config.level1.level2.level3.sequence=x",
        ],
    )
    assert result.level1.level2.level3.value == 100  # type: ignore

    # Access sequence
    sequence_value = result.level1.level2.level3.sequence  # type: ignore
    assert isinstance(sequence_value, tuple)  # Will be cast to tuple because frozen!
    assert len(sequence_value) == 1
    assert sequence_value[0] == "x"

    # Test helptext
    helptext = get_helptext_with_checks(nested_fn)
    assert "--config.level1.level2.level3.value" in helptext
    assert "--config.level1.level2.level3.sequence" in helptext


def test_frozenconfigdict_in_dataclass() -> None:
    """Test FrozenConfigDict as a field within a dataclass."""
    from ml_collections import FrozenConfigDict

    def get_config() -> FrozenConfigDict:
        config_dict = {}
        config_dict["policy_layer_dims"] = (128,) * 3
        config_dict["value_layer_dims"] = (256,) * 2
        return FrozenConfigDict(config_dict)

    @dataclasses.dataclass
    class TrainingConfig:
        learning_rate: float = 0.001
        batch_size: int = 64
        network: FrozenConfigDict = dataclasses.field(default_factory=get_config)

    # Create a test function that uses the dataclass with a FrozenConfigDict
    def train_with_config(config: FrozenConfigDict = get_config()) -> FrozenConfigDict:
        return config

    # Test with pure FrozenConfigDict
    result = tyro.cli(
        train_with_config,
        args=[
            "--config.policy-layer-dims=64",
        ],
    )
    assert result.policy_layer_dims == (64,)
    assert result.value_layer_dims == (256, 256)

    # Test helptext
    helptext = get_helptext_with_checks(train_with_config)
    assert "--config.policy-layer-dims" in helptext
    assert "--config.value-layer-dims" in helptext


def test_frozenconfigdict_with_tuples() -> None:
    """Test FrozenConfigDict with tuple fields of different types."""
    from ml_collections import FrozenConfigDict

    def get_config() -> FrozenConfigDict:
        config_dict = {}
        config_dict["int_tuple"] = (1, 2, 3)
        config_dict["float_tuple"] = (1.0, 2.0, 3.0)
        config_dict["str_tuple"] = ("a", "b", "c")
        config_dict["mixed_tuple"] = (1, "a", 2.0)
        return FrozenConfigDict(config_dict)

    def process(config: FrozenConfigDict = get_config()) -> FrozenConfigDict:
        return config

    # Test various tuple types
    result = tyro.cli(
        process,
        args=[
            "--config.int-tuple=10",
            "--config.float-tuple=1.5",
            "--config.str-tuple=x",
            "--config.mixed-tuple",
            "5",
            "3",
            "1",
        ],
    )
    assert result.int_tuple == (10,)
    assert result.float_tuple == (1.5,)
    assert result.str_tuple == ("x",)
    assert result.mixed_tuple == (5, "3", 1.0)

    # Test helptext
    helptext = get_helptext_with_checks(process)
    assert "--config.int-tuple" in helptext
    assert "--config.float-tuple" in helptext
    assert "--config.str-tuple" in helptext
