Great investigation @tim!

We have multiple options for changes in DC/OS E2E, including the following:

1. Use a log handler which is OK with a timeout error being raised by another thread

The problem with this is that such a log handler must be used by every consumer of DC/OS E2E.
This is not good.

2. Change DC/OS E2E's ``wait_for_dcos_*`` to work in a single thread

This would have no user impact.
We can make each step of the ``wait_for_dcos_*`` methods take a timeout parameter.
This is trivial except for the call to DC/OS Test Utils' ``wait_for_dcos`` method.

    2a. By changing DC/OS Test Utils' ``wait_for_dcos`` method to take a timeout parameter.

        * This involves changing all methods called by ``wait_for_dcos`` and giving each one a timeout parameter.
        * This involves changing ``wait_for_dcos`` to keep track of the total timeout across methods.

    2b. By using just DC/OS Checks and removing the use of DC/OS Test Utils in ``wait_for_dcos_ee``.

        This would involve:

        * Removing DC/OS 1.9 DC/OS Enterprise support from DC/OS E2E.
          - Change documentation to recommend last supported version of DC/OS E2E
          - Remove tests for DC/OS Enterprise 1.9
        * Backporting relevant DC/OS checks to 1.10, 1.11, 1.12 (see DCOS-44512)
        * Add a new check in DC/OS E2E - we need to wait for all known agents to spin up and connect to Mesos
          - Copy this from dcos-test-utils:
            - https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L357
            - https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L271
        * Merge ``wait_for_dcos_oss`` and ``wait_for_dcos_ee``.
        * Change DC/OS E2E CLI tools to not require username and password for ``wait`` commands.
        * Change DC/OS E2E CLI tools to not have to know whether the cluster is OSS or Enterprise.


Let's consider the trade-offs between (2a) and (2b):

(2a) - Pro: We benefit all consumers of DC/OS Test Utils
(2a) - Pro: We keep DC/OS 1.9 support in DC/OS E2E
(2a) - Pro: We benefit users of DC/OS E2E who use DC/OS OSS.

(2b) - Pro: Side-effect of helping customers and our support team and us when debugging issues in 1.10, 1.11 and 1.12 by making the DC/OS issues transparent through the dcos-checks-nodepoststart journald logs.
(2b) - Pro: Complexity of the code goes down as we only have to reason about one kind of checks as we wait for DC/OS Enterprise.
(2b) - Pro: Complexity of the code goes down as we treat all clusters, once created, equally, OSS or Enterprise.
(2b) - Pro: In the future, this will allow us to have the same code for ``wait_for_dcos_oss`` and ``wait_for_dcos_enterprise``. This requires service accounts on DC/OS OSS (DCOS-17898).
(2b) - Pro: When DC/OS OSS get service accounts we can remove ``wait_for_dcos`` from dcos-test-utils, leaving it as a DC/OS API library with significantly reduced scope for the Security team to support.

Conclusions:

(2b) - This is a fix for technical debt and has great user and developer benefits.
(2a) - Will help in some situations where (2b) does not.

If we want to accelerate and improve our situation in the future we would do (2a) and (2b).

