"""
Tests for Homebrew and Linuxbrew.
"""

import logging
import subprocess
from pathlib import Path
from typing import Set

import docker
from docker.types import Mount
from dulwich.repo import Repo
from py.path import local  # pylint: disable=no-name-in-module, import-error

from admin.homebrew import get_homebrew_formula


LOGGER = logging.getLogger(__name__)


def test_brew(tmpdir: local) -> None:
    """
    It is possible to create a Homebrew formula and to install this with
    Linuxbrew.
    """
    # Homebrew requires the archive name to look like a valid version.
    version = '1'
    archive_name = '{version}.tar.gz'.format(version=version)
    local_repository = Repo('.')
    archive_file = Path(str(tmpdir.join(archive_name)))
    archive_file.touch()
    # We do not use ``dulwich.porcelain.archive`` because it has no option to
    # use a gzip format.
    args = [
        'git',
        'archive',
        '--format',
        'tar.gz',
        '-o',
        str(archive_file),
        '--prefix',
        '{version}/'.format(version=version),
        'HEAD',
    ]
    subprocess.run(args=args, check=True)

    client = docker.from_env(version='auto')
    linuxbrew_image = 'linuxbrew/linuxbrew'
    # The path needs to look like a versioned artifact to Linuxbrew.
    container_archive_path = '/' + archive_name
    archive_url = 'file://' + container_archive_path
    head_url = 'file://' + str(Path(local_repository.path).absolute())

    homebrew_formula_contents = get_homebrew_formula(
        archive_url=archive_url,
        head_url=head_url,
    )

    homebrew_filename = 'dcose2e.rb'
    homebrew_file = Path(str(tmpdir.join(homebrew_filename)))
    homebrew_file.write_text(homebrew_formula_contents)
    container_homebrew_file_path = '/' + homebrew_filename

    archive_mount = Mount(
        source=str(archive_file.absolute()),
        target=container_archive_path,
        type='bind',
    )

    homebrew_file_mount = Mount(
        source=str(homebrew_file.absolute()),
        target=container_homebrew_file_path,
        type='bind',
    )

    mounts = [archive_mount, homebrew_file_mount]
    command_list = [
        'brew',
        'install',
        container_homebrew_file_path,
        '&&',
        'dcos-docker',
        '--help',
        '&&',
        'dcos-aws',
        '--help',
        '&&',
        'dcos-vagrant',
        '--help',
    ]

    command = '/bin/bash -c "{command}"'.format(
        command=' '.join(command_list),
    )

    client.containers.run(
        image=linuxbrew_image,
        mounts=mounts,
        command=command,
        environment={'HOMEBREW_NO_AUTO_UPDATE': 1},
        remove=True,
    )


def make_linux_binaries() -> Set[Path]:
    """
    Create binaries for Linux in a Docker container.
    """

    repo_root = Path(__file__).parent.parent.parent
    target_dir = '/e2e'
    code_mount = Mount(
        source=str(repo_root.absolute()),
        target=target_dir,
        type='bind',
    )

    binaries = ('dcos-docker', 'dcos-vagrant', 'dcos-aws')

    cmd_in_container = ['pip3', 'install', '-e', '.[packaging]']
    for binary in binaries:
        cmd_in_container += ['&&', 'pyinstaller', './bin/{binary}'.format(binary=binary), '--onefile',]
    cmd = 'bash -c "{cmd}"'.format(cmd=' '.join(cmd_in_container))

    client = docker.from_env(version='auto')
    container = client.containers.run(
        image='python:3.6',
        mounts=[code_mount],
        command=cmd,
        working_dir=target_dir,
        remove=True,
        detach=True,
    )
    for line in container.logs(stream=True):
        line = line.decode().strip()
        LOGGER.info(line)

    dist_dir = repo_root / 'dist'
    binary_paths = set([])
    for binary in binaries:
        binary_paths.add(dist_dir / binary)

    return binary_paths


def test_pyinstaller() -> None:
    binary_paths = make_linux_binaries()
    # container = new_linux_container()
    # copy_to(container, [binary_packages])
    # container.run(install_cmds)
    # container.run(check_working)
