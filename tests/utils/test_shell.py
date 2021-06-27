import os

from pathlib import Path
from unittest import mock

import pytest

from poetry.utils.env import VirtualEnv
from poetry.utils.shell import WINDOWS
from poetry.utils.shell import Shell as _Shell


@pytest.fixture
def Shell():
    _Shell._shell = None
    return _Shell


@pytest.fixture
def set_SHELL_environment_variable():
    environ = dict(os.environ)

    VAR = "SHELL" if os.name == "posix" else "COMSPEC"
    os.environ[VAR] = "/blah/blah/blah/name"

    yield

    os.environ.clear()
    os.environ.update(environ)


@pytest.fixture
def env():
    return VirtualEnv(path=Path("/prefix"), base=Path("/base/prefix"))


@pytest.fixture
def MockedSpawn():
    class _Spawn:
        def __init__(self, command, args=[], dimensions=None):
            self.exitstatus = 42
            self._log = {
                "setecho": [],
                "sendline": [],
                "setwinsize": [],
                "interact": [],
                "close": [],
            }

        def setecho(self, *args, **kwargs):
            self._log["setecho"].append((args, kwargs))

        def sendline(self, *args, **kwargs):
            self._log["sendline"].append((args, kwargs))

        def setwinsize(self, *args, **kwargs):
            self._log["setwinsize"].append((args, kwargs))

        def interact(self, *args, **kwargs):
            self._log["interact"].append((args, kwargs))

        def close(self, *args, **kwargs):
            self._log["close"].append((args, kwargs))

    return _Spawn


def test_name_and_path_properties(Shell):
    """
    Given a Shell object,
    Check that the name and path propterites
        match the _name and _path attributes,
        as well as the values passed in.
    """
    s = Shell(name="name", path="path")
    assert s.name == s._name == "name"
    assert s.path == s._path == "path"


def test_default_shell_is_None(Shell):
    """
    Given the Shell class,
    Check that _shell is None
    """
    assert Shell._shell is None


def test_get_when__shell_is_not_none(Shell):
    """
    Given the Shell class, when _shell is not None,
    Check that the get class method returns Shell._shell
    """
    s = Shell(name="name", path="path")
    Shell._shell = s
    assert Shell.get() == s


def test_get_when_detect_shell_works(Shell, mocker):
    """
    Given the Shell class,
    When Shell.get() is called, and shellingham.detect_shell()
        doesn't error.
    Check that the resulting shell's name and path are as expected,
        and that Shell._shell is updated.
    """
    mocker.patch(
        "poetry.utils.shell.detect_shell", return_value=("Mocked Name", "Mocked Path")
    )
    s = Shell.get()
    assert s.name == "Mocked Name"
    assert s.path == "Mocked Path"
    assert Shell._shell == s


def test_get_when_detect_shell_raises_error(
    Shell, mocker, set_SHELL_environment_variable
):
    """
    Given the Shell Class running on a posix system.
    When Shell.get() is called, and shellingham.detect_shell()
        raises an error, but os.environ.get is not None.
    Check that the resulting shell is as expected.
    """
    mocker.patch("poetry.utils.shell.detect_shell", side_effect=RuntimeError)

    s = Shell.get()
    assert s.name == "name"
    assert s.path == "/blah/blah/blah/name"
    assert Shell._shell == s


def test_get_when_detect_shell_raises_error_and_os_environ_get_returns_None(
    Shell, mocker, set_SHELL_environment_variable
):
    """
    Given the Shell Class.
    When Shell.get() is called, shellingham.detect_shell() raises
        an error, and os.environ.get returns None (i.e. SHELL or
        COMSPEC environment variable isn't set).
    Check that RuntimeError is raised.
    """
    mocker.patch("poetry.utils.shell.detect_shell", side_effect=RuntimeError)

    del os.environ["SHELL" if os.name == "posix" else "COMSPEC"]

    excinfo = pytest.raises(RuntimeError, Shell.get)
    assert "Unable to detect the current shell." in str(excinfo)


@pytest.mark.parametrize(
    "s_name,suffix",
    [
        pytest.param("fish", ".fish", id="fish"),
        pytest.param("csh", ".csh", id="csh"),
        pytest.param("tcsh", ".csh", id="tcsh"),
        pytest.param("Anything Else", "", id="Default Case"),
    ],
)
def test__get_activate_script(s_name, suffix, Shell):
    """
    Given a Shell,
    Check that s._get_activate_script() returns the correct script.
    """
    s = Shell(name=s_name, path="path")
    assert s._get_activate_script() == "activate" + suffix


@pytest.mark.parametrize(
    "s_name,command",
    [
        pytest.param("fish", "source", id="fish"),
        pytest.param("csh", "source", id="csh"),
        pytest.param("tcsh", "source", id="tcsh"),
        pytest.param("Anything Else", ".", id="Default Case"),
    ],
)
def test__get_source_command(s_name, command, Shell):
    """
    Given a Shell,
    Check that s._get_source_command returns the correct command.
    """
    s = Shell(name=s_name, path="path")
    assert s._get_source_command() == command


@pytest.mark.skipif(not WINDOWS, reason="Windows specific path")
def test_activate_if_windows(env, Shell, mocker):
    """
    Given a Shell object on windows,
    When shell.activate(env) is called,
    Check that env.execute(shell.path) is called.
    """
    s = Shell("name", "path")

    with mock.patch.object(env, "execute", return_value=None) as env_execute:
        s.activate(env)
    assert env_execute.called_with("path")


@pytest.mark.skipif(WINDOWS, reason="Non-Windows specific path")
def test_activate_if_not_windows(env, Shell, mocker, MockedSpawn):
    """
    Given a Shell object on a non-windows system,
    When shell.activate(env) is called,
    Check that the correct methods are called on
    the mocked object returned by pexpect.spawn()
    """
    s = Shell("zsh", "path")
    spawn = MockedSpawn("command")
    mocker.patch("pexpect.spawn", return_value=spawn)

    with pytest.raises(SystemExit) as exeinfo:
        s.activate(env)

    expected = {
        "sendline": [((". /prefix/bin/activate",), {})],
        "setwinsize": [],
        "setecho": [((False,), {})],
        "interact": [((), {"escape_character": None})],
        "close": [((), {})],
    }

    assert spawn._log == expected
    assert exeinfo.value.code == 42


def test___repr__(Shell):
    s = Shell(name="NAME", path="PATH")
    assert repr(s) == 'Shell("NAME", "PATH")'