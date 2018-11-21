"""
Tools for destroying clusters.
"""

from typing import List

import click
from halo import Halo

from dcos_e2e_cli.common.options import existing_cluster_id_option
from dcos_e2e_cli.common.utils import check_cluster_id_exists

from ._common import ClusterVMs, existing_cluster_ids


@click.command('destroy-list')
@click.argument(
    'cluster_ids',
    nargs=-1,
    type=str,
)
@click.pass_context
def destroy_list(
    ctx: click.core.Context,
    cluster_ids: List[str],
) -> None:
    """
    Destroy clusters.

    To destroy all clusters, run
    ``minidcos vagrant destroy $(minidcos vagrant list)``.
    """
    for cluster_id in cluster_ids:
        if cluster_id not in existing_cluster_ids():
            warning = 'Cluster "{cluster_id}" does not exist'.format(
                cluster_id=cluster_id,
            )
            click.echo(warning, err=True)
            continue

        ctx.invoke(
            destroy,
            cluster_id=cluster_id,
        )


@click.command('destroy')
@existing_cluster_id_option
def destroy(cluster_id: str) -> None:
    """
    Destroy a cluster.
    """
    spinner_text = 'Destroying cluster "{cluster_id}"'.format(
        cluster_id=cluster_id,
    )
    spinner.start()
    check_cluster_id_exists(
        new_cluster_id=cluster_id,
        existing_cluster_ids=existing_cluster_ids(),
    )
    cluster_vms = ClusterVMs(cluster_id=cluster_id)
    cluster_vms.destroy()
    spinner.stop()
    click.echo(cluster_id)
