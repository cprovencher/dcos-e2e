"""
Tests for Sphinx version extensions.
"""

import subprocess
from pathlib import Path
from textwrap import dedent

# See https://github.com/PyCQA/pylint/issues/1536 for details on why the errors
# are disabled.
from py.path import local  # pylint: disable=no-name-in-module, import-error

import dcos_e2e


def test_version_prompt(tmpdir: local) -> None:
    """
    The ``version-prompt`` directive replaces the placeholder
    ``|release|`` in a source file with the current installable version in
    the output file.
    """
    version = dcos_e2e.__version__
    release = version.split('+')[0]
    source_directory = tmpdir.mkdir('source')
    source_file = source_directory.join('contents.rst')
    source_file_content = dedent(
        """\
        .. version-prompt:: bash $

           $ PRE-|release|-POST
        """,
    )
    source_file.write(source_file_content)
    destination_directory = tmpdir.mkdir('destination')
    args = [
        'sphinx-build',
        '-b',
        'html',
        # Do not look for config file, use -D flags instead.
        '-C',
        '-D',
        'extensions=dcos_e2e._sphinx_extensions',
        # Directory containing source and config files.
        str(source_directory),
        # Directory containing build files.
        str(destination_directory),
        # Source file to process.
        str(source_file),
    ]
    subprocess.check_output(args=args)
    expected = 'PRE-{release}-POST'.format(release=release)
    content_html = Path(str(destination_directory)) / 'contents.html'
    assert expected in content_html.read_text()