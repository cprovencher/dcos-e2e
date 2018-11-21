"""
Tools for creating a DC/OS cluster.
"""

# TODO when it succeeds, does it go to stdout / get captured?
# TODO how does it interact with -v

from halo import Halo

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import click
import docker
from docker.models.networks import Network
from docker.types import Mount

from dcos_e2e.backends import Docker
from dcos_e2e.cluster import Cluster
from dcos_e2e.node import Transport
from dcos_e2e_cli._vendor.dcos_installer_tools import DCOSVariant
from dcos_e2e_cli.common.arguments import installer_argument
from dcos_e2e_cli.common.create import create_cluster, get_config
from dcos_e2e_cli.common.options import (
    agents_option,
    cluster_id_option,
    copy_to_master_option,
    extra_config_option,
    genconf_dir_option,
    license_key_option,
    masters_option,
    public_agents_option,
    security_mode_option,
    variant_option,
    verbosity_option,
    workspace_dir_option,
)
from dcos_e2e_cli.common.utils import (
    check_cluster_id_unique,
    get_doctor_message,
    get_variant,
    install_dcos_from_path,
    set_logging,
    show_cluster_started_message,
    write_key_pair,
)

from ._common import (
    CLUSTER_ID_LABEL_KEY,
    DOCKER_STORAGE_DRIVERS,
    DOCKER_VERSIONS,
    LINUX_DISTRIBUTIONS,
    NODE_TYPE_AGENT_LABEL_VALUE,
    NODE_TYPE_LABEL_KEY,
    NODE_TYPE_MASTER_LABEL_VALUE,
    NODE_TYPE_PUBLIC_AGENT_LABEL_VALUE,
    VARIANT_ENTERPRISE_LABEL_VALUE,
    VARIANT_LABEL_KEY,
    VARIANT_OSS_LABEL_VALUE,
    WORKSPACE_DIR_LABEL_KEY,
    docker_client,
    existing_cluster_ids,
)
from ._options import node_transport_option
from .doctor import doctor
from .wait import wait


def _validate_docker_network(
    ctx: click.core.Context,
    param: Union[click.core.Option, click.core.Parameter],
    value: Any,
) -> Network:
    """
    Validate that a given network name is an existing Docker network name.
    """
    # We "use" variables to satisfy linting tools.
    for _ in (ctx, param):
        pass
    client = docker_client()
    try:
        return client.networks.get(network_id=value)
    except docker.errors.NotFound:
        message = (
            'No such Docker network with the name "{value}".\n'
            'Docker networks are:\n{networks}'
        ).format(
            value=value,
            networks='\n'.join(
                [network.name for network in client.networks.list()],
            ),
        )
        raise click.BadParameter(message=message)


def _validate_port_map(
    ctx: click.core.Context,
    param: Union[click.core.Option, click.core.Parameter],
    value: Any,
) -> Dict[str, int]:
    """
    Turn port map strings into a Dict that ``docker-py`` can use.
    """
    # We "use" variables to satisfy linting tools.
    for _ in (ctx, param):
        pass

    ports = {}  # type: Dict[str, int]
    for ports_definition in value:
        parts = ports_definition.split(':')

        # Consider support the full docker syntax.
        # https://docs.docker.com/engine/reference/run/#expose-incoming-ports
        if len(parts) != 2:
            message = (
                '"{ports_definition}" is not a valid port map. '
                'Please follow this syntax: <HOST_PORT>:<CONTAINER_PORT>'
            ).format(ports_definition=ports_definition)
            raise click.BadParameter(message=message)

        host_port, container_port = parts
        if not host_port.isdigit():
            message = 'Host port "{host_port}" is not an integer.'.format(
                host_port=host_port,
            )
            raise click.BadParameter(message=message)
        if not container_port.isdigit():
            message = ('Container port "{container_port}" is an integer.'
                       ).format(container_port=container_port)
            raise click.BadParameter(message=message)
        if int(host_port) < 0 or int(host_port) > 65535:
            message = ('Host port "{host_port}" is not a valid port number.'
                       ).format(host_port=host_port)
            raise click.BadParameter(message=message)
        if int(container_port) < 0 or int(container_port) > 65535:
            message = (
                'Container port "{container_port}" is not a valid port number.'
            ).format(container_port=container_port)
            raise click.BadParameter(message=message)

        key = container_port + '/tcp'
        if key in ports:
            message = (
                'Container port "{container_port}" specified multiple times.'
            ).format(container_port=container_port)
            raise click.BadParameter(message=message)

        ports[key] = int(host_port)
    return ports


def _validate_volumes(
    ctx: click.core.Context,
    param: Union[click.core.Option, click.core.Parameter],
    value: Any,
) -> List[docker.types.Mount]:
    """
    Turn volume definition strings into ``Mount``s that ``docker-py`` can use.
    """
    for _ in (ctx, param):
        pass
    mounts = []
    for volume_definition in value:
        parts = volume_definition.split(':')

        if len(parts) == 1:
            host_src = None
            [container_dst] = parts
            read_only = False
        elif len(parts) == 2:
            host_src, container_dst = parts
            read_only = False
        elif len(parts) == 3:
            host_src, container_dst, mode = parts
            if mode == 'ro':
                read_only = True
            elif mode == 'rw':
                read_only = False
            else:
                message = (
                    'Mode in "{volume_definition}" is "{mode}". '
                    'If given, the mode must be one of "ro", "rw".'
                ).format(
                    volume_definition=volume_definition,
                    mode=mode,
                )
                raise click.BadParameter(message=message)
        else:
            message = (
                '"{volume_definition}" is not a valid volume definition. '
                'See '
                'https://docs.docker.com/engine/reference/run/#volume-shared-filesystems '  # noqa: E501
                'for the syntax to use.'
            ).format(volume_definition=volume_definition)
            raise click.BadParameter(message=message)

        mount = docker.types.Mount(
            source=host_src,
            target=container_dst,
            type='bind',
            read_only=read_only,
        )
        mounts.append(mount)
    return mounts


def _add_authorized_key(cluster: Cluster, public_key_path: Path) -> None:
    """
    Add an authorized key to all nodes in the given cluster.
    """
    nodes = {
        *cluster.masters,
        *cluster.agents,
        *cluster.public_agents,
    }

    for node in nodes:
        node.run(
            args=['echo', '', '>>', '/root/.ssh/authorized_keys'],
            shell=True,
        )
        node.run(
            args=[
                'echo',
                public_key_path.read_text(),
                '>>',
                '/root/.ssh/authorized_keys',
            ],
            shell=True,
        )


@click.command('create')
@installer_argument
@click.option(
    '--docker-version',
    type=click.Choice(sorted(DOCKER_VERSIONS.keys())),
    default='1.13.1',
    show_default=True,
    help='The Docker version to install on the nodes.',
)
@click.option(
    '--linux-distribution',
    type=click.Choice(sorted(LINUX_DISTRIBUTIONS.keys())),
    default='centos-7',
    show_default=True,
    help='The Linux distribution to use on the nodes.',
)
@click.option(
    '--docker-storage-driver',
    type=click.Choice(sorted(DOCKER_STORAGE_DRIVERS.keys())),
    default=None,
    show_default=False,
    help=(
        'The storage driver to use for Docker in Docker. '
        "By default this uses the host's driver."
    ),
)
@masters_option
@agents_option
@public_agents_option
@extra_config_option
@security_mode_option
@cluster_id_option
@license_key_option
@genconf_dir_option
@copy_to_master_option
@workspace_dir_option
@click.option(
    '--custom-volume',
    type=str,
    callback=_validate_volumes,
    help=(
        'Bind mount a volume on all cluster node containers. '
        'See '
        'https://docs.docker.com/engine/reference/run/#volume-shared-filesystems '  # noqa: E501
        'for the syntax to use.'
    ),
    multiple=True,
)
@click.option(
    '--custom-master-volume',
    type=str,
    callback=_validate_volumes,
    help=(
        'Bind mount a volume on all cluster master node containers. '
        'See '
        'https://docs.docker.com/engine/reference/run/#volume-shared-filesystems '  # noqa: E501
        'for the syntax to use.'
    ),
    multiple=True,
)
@click.option(
    '--custom-agent-volume',
    type=str,
    callback=_validate_volumes,
    help=(
        'Bind mount a volume on all cluster agent node containers. '
        'See '
        'https://docs.docker.com/engine/reference/run/#volume-shared-filesystems '  # noqa: E501
        'for the syntax to use.'
    ),
    multiple=True,
)
@click.option(
    '--custom-public-agent-volume',
    type=str,
    callback=_validate_volumes,
    help=(
        'Bind mount a volume on all cluster public agent node containers. '
        'See '
        'https://docs.docker.com/engine/reference/run/#volume-shared-filesystems '  # noqa: E501
        'for the syntax to use.'
    ),
    multiple=True,
)
@variant_option
@click.option(
    '--wait-for-dcos',
    is_flag=True,
    help=(
        'Wait for DC/OS after creating the cluster. '
        'This is equivalent to using "minidcos docker wait" after this '
        'command. '
        '"minidcos docker wait" has various options available and so may be '
        'more appropriate for your use case. '
        'If the chosen transport is "docker-exec", this will skip HTTP checks '
        'and so the cluster may not be fully ready.'
    ),
)
@click.option(
    '--network',
    default='bridge',
    type=str,
    callback=_validate_docker_network,
    help=(
        'The Docker network containers will be connected to.'
        'It may not be possible to SSH to containers on a custom network on '
        'macOS. '
    ),
)
@node_transport_option
@click.option(
    '--one-master-host-port-map',
    type=str,
    callback=_validate_port_map,
    help=(
        'Publish a container port of one master node to the host. '
        'Only Transmission Control Protocol is supported currently. '
        'The syntax is <HOST_PORT>:<CONTAINER_PORT>'
    ),
    multiple=True,
)
@verbosity_option
@click.pass_context
def create(
    ctx: click.core.Context,
    agents: int,
    installer: str,
    cluster_id: str,
    docker_storage_driver: str,
    docker_version: str,
    extra_config: Dict[str, Any],
    linux_distribution: str,
    masters: int,
    public_agents: int,
    license_key: Optional[str],
    security_mode: Optional[str],
    copy_to_master: List[Tuple[Path, Path]],
    genconf_dir: Optional[Path],
    workspace_dir: Optional[Path],
    custom_volume: List[Mount],
    custom_master_volume: List[Mount],
    custom_agent_volume: List[Mount],
    custom_public_agent_volume: List[Mount],
    variant: str,
    transport: Transport,
    wait_for_dcos: bool,
    network: Network,
    one_master_host_port_map: Dict[str, int],
    verbose: int,
) -> None:
    """
    Create a DC/OS cluster.

        DC/OS Enterprise

            \b
            DC/OS Enterprise clusters require different configuration variables to DC/OS OSS.
            For example, enterprise clusters require the following configuration parameters:

            ``superuser_username``, ``superuser_password_hash``, ``fault_domain_enabled``, ``license_key_contents``

            \b
            These can all be set in ``--extra-config``.
            However, some defaults are provided for all but the license key.

            \b
            The default superuser username is ``admin``.
            The default superuser password is ``admin``.
            The default ``fault_domain_enabled`` is ``false``.

            \b
            ``license_key_contents`` must be set for DC/OS Enterprise 1.11 and above.
            This is set to one of the following, in order:

            \b
            * The ``license_key_contents`` set in ``--extra-config``.
            * The contents of the path given with ``--license-key``.
            * The contents of the path set in the ``DCOS_LICENSE_KEY_PATH`` environment variable.

            \b
            If none of these are set, ``license_key_contents`` is not given.
    """  # noqa: E501
    creating_spinner_text = 'Creating cluster configuration'
    configuration_spinner = Halo(text=creating_spinner_text, spinner='dots')
    configuration_spinner.start()

    set_logging(verbosity_level=verbose)
    check_cluster_id_unique(
        new_cluster_id=cluster_id,
        existing_cluster_ids=existing_cluster_ids(),
    )
    base_workspace_dir = workspace_dir or Path(tempfile.gettempdir())
    workspace_dir = base_workspace_dir / uuid.uuid4().hex

    doctor_message = get_doctor_message(sibling_ctx=ctx, doctor_command=doctor)
    ssh_keypair_dir = workspace_dir / 'ssh'
    ssh_keypair_dir.mkdir(parents=True)
    public_key_path = ssh_keypair_dir / 'id_rsa.pub'
    private_key_path = ssh_keypair_dir / 'id_rsa'
    write_key_pair(
        public_key_path=public_key_path,
        private_key_path=private_key_path,
    )

    installer_path = Path(installer).resolve()

    dcos_variant = get_variant(
        given_variant=variant,
        installer_path=installer_path,
        workspace_dir=workspace_dir,
        doctor_message=doctor_message,
    )

    files_to_copy_to_genconf_dir = []
    if genconf_dir is not None:
        container_genconf_path = Path('/genconf')
        for genconf_file in genconf_dir.glob('*'):
            genconf_relative = genconf_file.relative_to(genconf_dir)
            relative_path = container_genconf_path / genconf_relative
            files_to_copy_to_genconf_dir.append((genconf_file, relative_path))

    variant_label_value = {
        DCOSVariant.OSS: VARIANT_OSS_LABEL_VALUE,
        DCOSVariant.ENTERPRISE: VARIANT_ENTERPRISE_LABEL_VALUE,
    }[dcos_variant]

    cluster_backend = Docker(
        custom_container_mounts=custom_volume,
        custom_master_mounts=custom_master_volume,
        custom_agent_mounts=custom_agent_volume,
        custom_public_agent_mounts=custom_public_agent_volume,
        linux_distribution=LINUX_DISTRIBUTIONS[linux_distribution],
        docker_version=DOCKER_VERSIONS[docker_version],
        storage_driver=DOCKER_STORAGE_DRIVERS.get(docker_storage_driver),
        docker_container_labels={
            CLUSTER_ID_LABEL_KEY: cluster_id,
            WORKSPACE_DIR_LABEL_KEY: str(workspace_dir),
            VARIANT_LABEL_KEY: variant_label_value,
        },
        docker_master_labels={
            NODE_TYPE_LABEL_KEY: NODE_TYPE_MASTER_LABEL_VALUE,
        },
        docker_agent_labels={NODE_TYPE_LABEL_KEY: NODE_TYPE_AGENT_LABEL_VALUE},
        docker_public_agent_labels={
            NODE_TYPE_LABEL_KEY: NODE_TYPE_PUBLIC_AGENT_LABEL_VALUE,
        },
        workspace_dir=workspace_dir,
        transport=transport,
        network=network,
        one_master_host_port_map=one_master_host_port_map,
    )

    configuration_spinner.succeed(text='Configuration created')

    creating_spinner_text = 'Creating cluster nodes'
    create_nodes_spinner = Halo(text=creating_spinner_text, spinner='dots')
    create_nodes_spinner.start()

    cluster = create_cluster(
        cluster_backend=cluster_backend,
        masters=masters,
        agents=agents,
        public_agents=public_agents,
        sibling_ctx=ctx,
        doctor_command=doctor,
    )

    _add_authorized_key(cluster=cluster, public_key_path=public_key_path)

    for node in cluster.masters:
        for path_pair in copy_to_master:
            local_path, remote_path = path_pair
            node.send_file(
                local_path=local_path,
                remote_path=remote_path,
            )

    create_nodes_spinner.succeed(text='Cluster nodes created')
    dcos_config = get_config(
        cluster=cluster,
        extra_config=extra_config,
        dcos_variant=dcos_variant,
        security_mode=security_mode,
        license_key=license_key,
    )

    install_dcos_from_path(
        cluster=cluster,
        dcos_config=dcos_config,
        ip_detect_path=cluster_backend.ip_detect_path,
        files_to_copy_to_genconf_dir=files_to_copy_to_genconf_dir,
        doctor_command=doctor,
        sibling_ctx=ctx,
        installer=installer_path,
    )

    if wait_for_dcos:
        ctx.invoke(
            wait,
            cluster_id=cluster_id,
            transport=transport,
            skip_http_checks=bool(transport == Transport.DOCKER_EXEC),
            verbose=verbose,
        )
        return

    show_cluster_started_message(
        # We work on the assumption that the ``wait`` command is a sibling
        # command of this one.
        sibling_ctx=ctx,
        wait_command=wait,
        cluster_id=cluster_id,
    )

    click.echo(cluster_id)
