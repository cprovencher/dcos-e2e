``dcos-aws`` CLI
================

The ``dcos-aws`` CLI allows you to create and manage open source DC/OS and DC/OS Enterprise clusters on AWS EC2 instances.

A typical CLI workflow for open source DC/OS may look like the following.
:ref:`Install the CLI <installation>`, then create and manage a cluster:

.. code-block:: console

   # Fix issues shown by dcos-aws doctor
   $ dcos-aws doctor
   $ dcos-aws create https://downloads.dcos.io/dcos/stable/dcos_generate_config.sh --agents 0
   default
   $ dcos-aws wait
   $ dcos-aws run --sync-dir /path/to/dcos/checkout pytest -k test_tls
   ...

Each of these and more are described in detail below.

.. contents::
   :local:

.. include:: aws-backend-requirements.rst

.. include:: install-cli.rst

Creating a Cluster
------------------

To create a cluster you first need the link to a DC/OS release artifact.

These can be found on `the releases page <https://dcos.io/releases/>`__.

`DC/OS Enterprise <https://mesosphere.com/product/>`__ is also supported.
Ask your sales representative for release artifacts.

Creating a cluster is possible with the :ref:`dcos-aws-create` command.
This command allows you to customize the cluster in many ways.

The command returns when the DC/OS installation process has started.
To wait until DC/OS has finished installing, use the :ref:`dcos-aws-wait` command.

To use this cluster, it is useful to find details using the :ref:`dcos-aws-inspect` command.

DC/OS Enterprise
~~~~~~~~~~~~~~~~

There are multiple DC/OS Enterprise-only features available in :ref:`dcos-aws-create`.

The only extra requirement is to give a valid license key, for DC/OS 1.11+.
See :ref:`dcos-aws-create` for details on how to provide a license key.

Ask your sales representative for DC/OS Enterprise release artifacts.

For, example, run the following to create a DC/OS Enterprise cluster in strict mode:

.. code-block:: console

   $ dcos-aws create $DCOS_ENTERPRISE_URL --variant enterprise \
        --license-key /path/to/license.txt \
        --security-mode strict

The command returns when the DC/OS installation process has started.
To wait until DC/OS has finished installing, use the :ref:`dcos-aws-wait` command.

See :ref:`dcos-aws-create` for details on this command and its options.

Cluster IDs
-----------

Clusters have unique IDs.
Multiple commands take ``--cluster-id`` options.
Specify a cluster ID in :ref:`dcos-aws-create`, and then use it in other commands.
Any command which takes a ``--cluster-id`` option defaults to using "default" if no cluster ID is given.

Running commands on Cluster Nodes
---------------------------------

It is possible to run commands on a cluster node in multiple ways.
These include using :ref:`dcos-aws-run` and ``ssh``.

Running commands on a cluster node using :ref:`dcos-aws-run`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to run the following to run a command on an arbitrary master node.

.. code-block:: console

   $ dcos-aws run systemctl list-units

See :ref:`dcos-aws-run` for more information on this command.

Running commands on a cluster node using ``ssh``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One SSH key allows access to all nodes in the cluster.
See this SSH key's path and the IP addresses of nodes using :ref:`dcos-aws-inspect`.

Getting on to a Cluster Node
----------------------------

Sometimes it is useful to get onto a cluster node.
To do this, you can use any of the ways of :ref:`running-commands`.

For example, to use :ref:`dcos-aws-run` to run ``bash`` to get on to an arbitrary master node:

.. code-block:: console

   $ dcos-aws run bash

Destroying Clusters
-------------------

Destroying clusters is not currently supported.

Running Integration Tests
-------------------------

The :ref:`dcos-aws-run` command is useful for running integration tests.

To run integration tests which are developed in the a DC/OS checkout at :file:`/path/to/dcos`, you can use the following workflow:

.. code-block:: console

   $ dcos-aws create https://downloads.dcos.io/dcos/stable/dcos_generate_config.sh
   $ dcos-aws wait
   $ dcos-aws run --sync-dir /path/to/dcos/checkout pytest -k test_tls.py

There are multiple options and shortcuts for using these commands.
See :ref:`dcos-aws-run` for more information on this command.

Viewing the Web UI
------------------

To view the web UI of your cluster, use the :ref:`dcos-aws-web` command.
To see the web UI URL of your cluster, use the :ref:`dcos-aws-inspect` command.

Before viewing the UI, you may first need to `configure your browser to trust your DC/OS CA <https://docs.mesosphere.com/1.11/security/ent/tls-ssl/ca-trust-browser/>`_, or choose to override the browser protection.

Using a Custom CA Certificate
-----------------------------

On DC/OS Enterprise clusters, it is possible to use a custom CA certificate.
See `the Custom CA certificate documentation <https://docs.mesosphere.com/1.11/security/ent/tls-ssl/ca-custom>`_ for details.
It is possible to use :ref:`dcos-aws-create` to create a cluster with a custom CA certificate.

#. Create or obtain the necessary files:

   :file:`dcos-ca-certificate.crt`, :file:`dcos-ca-certificate-key.key`, and :file:`dcos-ca-certificate-chain.crt`.

#. Put the above-mentioned files into a directory, e.g. :file:`/path/to/genconf/`.

#. Create a file containing the "extra" configuration.

   :ref:`dcos-aws-create` takes an ``--extra-config`` option.
   This adds the contents of the specified YAML file to a minimal DC/OS configuration.

   Create a file with the following contents:

   .. code:: yaml

      ca_certificate_path: genconf/dcos-ca-certificate.crt
      ca_certificate_key_path: genconf/dcos-ca-certificate-key.key
      ca_certificate_chain_path: genconf/dcos-ca-certificate-chain.crt

#. Create a cluster.

   .. code:: console

      dcos-aws create \
          $DCOS_ENTERPRISE_URL \
          --genconf-dir /path/to/genconf/ \
          --copy-to-master /path/to/genconf/dcos-ca-certificate-key.key:/var/lib/dcos/pki/tls/CA/private/custom_ca.key \
          --license-key /path/to/license.txt \
          --extra-config config.yml

#. Verify that everything has worked.

   See `Verify installation <https://docs.mesosphere.com/1.11/security/ent/tls-ssl/ca-custom/#verify-installation>`_ for steps to verify that the DC/OS Enterprise cluster was installed properly with the custom CA certificate.

CLI Reference
-------------

.. click:: cli:dcos_aws
  :prog: dcos-aws

.. _dcos-aws-create:

.. click:: cli.dcos_aws:create
  :prog: dcos-aws create

.. _dcos-aws-doctor:

.. click:: cli.dcos_aws:doctor
  :prog: dcos-aws doctor

.. click:: cli.dcos_aws:list_clusters
  :prog: dcos-aws list

.. _dcos-aws-run:

.. click:: cli.dcos_aws:run
  :prog: dcos-aws run

.. _dcos-aws-inspect:

.. click:: cli.dcos_aws:inspect_cluster
  :prog: dcos-aws inspect

.. click:: cli.dcos_aws:sync_code
  :prog: dcos-aws sync

.. _dcos-aws-wait:

.. click:: cli.dcos_aws:wait
  :prog: dcos-aws wait

.. _dcos-aws-web:

.. click:: cli.dcos_aws:web
  :prog: dcos-aws web

.. click:: cli.dcos_vagrant:destroy
  :prog: dcos-vagrant destroy

.. _dcos-vagrant-destroy-list:

.. click:: cli.dcos_vagrant:destroy_list
  :prog: dcos-vagrant destroy-list
