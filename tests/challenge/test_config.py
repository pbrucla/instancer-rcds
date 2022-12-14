import pytest  # type: ignore

import rcds
import rcds.errors
from rcds import Project
from rcds.challenge import config


@pytest.fixture
def test_datadir(request, datadir):
    fn_name = request.function.__name__
    assert fn_name[:5] == "test_"
    return datadir / fn_name[5:].replace("_", "-")


@pytest.fixture(scope="function")
def project(datadir):
    return Project(datadir)


@pytest.fixture
def configloader(project):
    return config.ConfigLoader(project)


def test_valid(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is None
    assert cfg["flag"] == "flag{test_flag_here}"


def test_schema_fail(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    assert (
        sum([1 for e in errors if isinstance(e, rcds.errors.SchemaValidationError)]) > 0
    )


def test_expose_no_containers(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    error_messages = [str(e) for e in errors]
    assert len(errors) != 0
    assert "Cannot expose ports without containers defined" in error_messages
    assert sum([1 for e in errors if isinstance(e, config.TargetNotFoundError)]) == 1


def test_nonexistent_target_container(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    error_messages = [str(e) for e in errors]
    assert len(errors) != 0
    assert (
        '`expose` references container "main" but it is not defined in `containers`'
        in error_messages
    )
    assert sum([1 for e in errors if isinstance(e, config.TargetNotFoundError)]) == 1


def test_nonexistent_target_port(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    error_messages = [str(e) for e in errors]
    assert len(errors) != 0
    assert (
        '`expose` references port 1 on container "main" which is not defined'
        in error_messages
    )
    assert sum([1 for e in errors if isinstance(e, config.TargetNotFoundError)]) == 1


def test_nonexistent_provide_file(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    error_messages = [str(e) for e in errors]
    assert len(errors) != 0
    assert (
        '`provide` references file "nonexistent" which does not exist' in error_messages
    )
    assert (
        sum([1 for e in errors if isinstance(e, config.TargetFileNotFoundError)]) == 1
    )


def test_nonexistent_flag_file(configloader, test_datadir) -> None:
    cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is not None
    assert cfg is None
    errors = list(errors)
    error_messages = [str(e) for e in errors]
    assert len(errors) != 0
    assert (
        '`flag.file` references file "nonexistent" which does not exist'
        in error_messages
    )
    assert (
        sum([1 for e in errors if isinstance(e, config.TargetFileNotFoundError)]) == 1
    )


def test_warn_multiline_flag(configloader, test_datadir) -> None:
    with pytest.warns(
        RuntimeWarning, match=r"^Flag contains multiple lines; is this intended\?$"
    ):
        cfg, errors = configloader.check_config(test_datadir / "challenge.yml")
    assert errors is None


def test_default_category(configloader, test_datadir) -> None:
    cfg = configloader.load_config(test_datadir / "chall" / "challenge.yml")
    assert cfg is not None
    assert cfg["category"] == "default-category"


def test_no_default_category(configloader, test_datadir) -> None:
    cfg = configloader.load_config(test_datadir / "challenge.yml")
    assert cfg is not None
    assert "category" not in cfg


def test_load_valid(configloader: config.ConfigLoader, datadir) -> None:
    cfg = configloader.load_config(datadir / "valid" / "challenge.yml")
    assert cfg is not None


def test_load_invalid(configloader: config.ConfigLoader, datadir) -> None:
    with pytest.raises(rcds.errors.ValidationError):
        configloader.load_config(datadir / "nonexistent-flag-file" / "challenge.yml")


class TestProjectDefaults:
    @staticmethod
    def test_omnibus(project: Project, datadir) -> None:
        project.config["defaults"] = {
            "containers": {
                "resources": {
                    "limits": {"cpu": "10m", "memory": "10Mi"},
                    "requests": {"cpu": "10m", "memory": "10Mi"},
                }
            },
            "expose": {"foo": "bar"},
            "value": 100,
        }
        configloader = config.ConfigLoader(project)
        cfg1 = configloader.load_config(datadir / "defaults" / "1" / "challenge.yml")
        assert cfg1["value"] == 100
        assert cfg1["containers"]["main"] == {
            "image": "gcr.io/google-samples/hello-app",
            "resources": {
                "limits": {"cpu": "10m", "memory": "10Mi"},
                "requests": {"cpu": "10m", "memory": "10Mi"},
            },
            "ports": [80],
            "replicas": 1,
        }
        assert cfg1["containers"]["partial"] == {
            "image": "gcr.io/google-samples/hello-app",
            "resources": {
                "limits": {"cpu": "20m", "memory": "10Mi"},
                "requests": {"cpu": "10m", "memory": "10Mi"},
            },
            "ports": [80],
            "replicas": 1,
        }
        assert cfg1["expose"]["main"][0] == {"target": 80, "tcp": 31525, "foo": "bar"}
        assert cfg1["expose"]["partial"][0] == {
            "target": 80,
            "tcp": 31546,
            "foo": "baz",
        }
        cfg2 = configloader.load_config(datadir / "defaults" / "2" / "challenge.yml")
        assert cfg2["value"] == 100


class TestFlagFormat:
    @staticmethod
    def test_valid_flag(project: Project, datadir) -> None:
        project.config["flagFormat"] = r"flag\{[a-z]*\}"
        configloader = config.ConfigLoader(project)
        cfg, errors = configloader.check_config(
            datadir / "flag-format" / "valid" / "challenge.yml"
        )
        assert cfg is not None
        assert errors is None

    @staticmethod
    def test_invalid_flag(project: Project, datadir) -> None:
        project.config["flagFormat"] = r"flag\{[a-z]*\}"
        configloader = config.ConfigLoader(project)
        cfg, errors = configloader.check_config(
            datadir / "flag-format" / "invalid" / "challenge.yml"
        )
        assert errors is not None
        assert cfg is None
        errors = list(errors)
        error_messages = [str(e) for e in errors]
        assert len(errors) != 0
        assert 'Flag "flag{1234}" does not match the flag format' in error_messages
        assert sum([1 for e in errors if isinstance(e, config.InvalidFlagError)]) == 1
