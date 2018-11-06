Great investigation @tim!

The following is the result of a discussion with Tim.

We have multiple options for changes in DC/OS E2E, including the following:

1. Use a log handler which is OK with a timeout error being raised from a co-routine.

The problem with this is that such a log handler must be used by every consumer of DC/OS E2E.
This is not good.

2. Change DC/OS E2E's {{wait_for_dcos_*}} to work without co-routines.

This would have no user impact.
We can make each step of the {{wait_for_dcos_*}} methods take a timeout parameter.
This is trivial except for the call to DC/OS Test Utils' {{wait_for_dcos}} method.

2a. By changing DC/OS Test Utils' {{wait_for_dcos}} method to take a timeout parameter.

    * This involves changing all methods called by {{wait_for_dcos}} and giving each one a timeout parameter.
    * This involves changing {{wait_for_dcos}} to keep track of the total timeout across methods.

2b. By using just DC/OS Checks and removing the use of DC/OS Test Utils' {{wait_for_dcos}} in {{wait_for_dcos_ee}}.

    This would involve:

    * Removing DC/OS 1.9 DC/OS Enterprise support from DC/OS E2E.
      - Change documentation to recommend last supported version of DC/OS E2E
      - Remove tests for DC/OS Enterprise 1.9
    * Backporting relevant DC/OS checks to 1.10, 1.11, 1.12 (see DCOS-44512)

    * Reimplement the wait for Mesos to show all agents in the {{/mesos/master/slaves}} endpoint response.
      The originals are [here|https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L357]
      and [here|https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L271].

2c. By using just DC/OS Checks and removing the use of DC/OS Test Utils' {{wait_for_dcos}} and tokens in {{wait_for_dcos_ee}}.

    See (2b).
    In addition, find a way to wait for Mesos to show all agents in the {{/mesos/master/slaves}} endpoint response without a DC/OS token.

    This involves:

    * Reimplement the wait for Mesos to show all agents in the {{/mesos/master/slaves}} endpoint response.
      The originals are [here|https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L357]
      and [here|https://github.com/dcos/dcos-test-utils/blob/c45478e88b9068fa307794d4eb0db2a95798d4a6/dcos_test_utils/dcos_api.py#L271].
      This rewrite will not involve using a token to make HTTP requests, and therefore it will not need a superuser username and password.
    * Merge {{wait_for_dcos_oss}} and {{wait_for_dcos_ee}}.
    * Change DC/OS E2E CLI tools to not require username and password for {{wait}} commands.
    * Change DC/OS E2E CLI tools to not have to know whether the cluster is OSS or Enterprise.
      

Let's consider the trade-offs between (2a) and (2b):

(2a) - Pro: We benefit all consumers of DC/OS Test Utils
(2a) - Pro: We keep DC/OS 1.9 support in DC/OS E2E
(2a) - Pro: We benefit users of DC/OS E2E who use DC/OS OSS.

(2b) - Pro: Side-effect of helping customers and our support team and us when debugging issues in 1.10, 1.11 and 1.12 by making the DC/OS issues transparent through the {{dcos-checks-nodepoststart}} {{journald}} logs.

(2c) - Pro: Side-effect of helping customers and our support team and us when debugging issues in 1.10, 1.11 and 1.12 by making the DC/OS issues transparent through the {{dcos-checks-nodepoststart}} {{journald}} logs.
(2c) - Pro: Complexity of the code goes down as we only have to reason about one kind of checks as we wait for DC/OS Enterprise.
(2c) - Pro: Complexity of the code goes down as we treat all clusters, once created, equally, OSS or Enterprise.
(2c) - Pro: In the future, this will allow us to have the same code for {{wait_for_dcos_oss}} and {{wait_for_dcos_enterprise}}.
       This requires service accounts on DC/OS OSS (DCOS-17898).
(2c) - Pro: When DC/OS OSS get service accounts we are closer to removing {{wait_for_dcos}} from {{dcos-test-utils}},
       leaving it as a DC/OS API library with significantly reduced scope for the Security team to support.

Conclusions:

(2c) - This is a fix for technical debt and has great user and developer benefits.
(2b) - This is a fix for technical debt and has some user and developer benefits.
(2a) - Will help in some situations where (2b) does not yet until OSS service accounts are merged.

If we want to accelerate and improve our situation in the future we would do all of these.
Let's start with (2b) as it is simple, and then decide what to do after that.
