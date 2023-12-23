# Database Tables

This section describes database tables for netUnicorn platform, including their structure and what manual modifications could be useful there.

All tables could be created using `netunicorn-director/scripts/dbdeploy.sql` script.

## Authentication

Stores usernames, password hashes, and sudo privileges flag for users. See [Users Management](users.md) for more details.

You need to manually modify this table to add, modify, or delete netUnicorn users.

## Experiments

Stores all information about all experiments ever created in the system. Deleted experiments are not deleted and reassigned to usernames starting with `deleted_`.

You might want to manually modify this table to change the Experiment status or to delete an experiment. See <a href="(../../../_autosummary/netunicorn.base.experiment.ExperimentStatus.html">ExperimentStatus</a> for possible status integer values.

## Locks

This table stores information what node is currently locked by any experiment. You might want to modify this table manually to remove locks after different kinds of failures.

## Compliations

This table stores information about all Docker compilation requests and their statuses.

## Executors

This table stores information about executors created, their statuses, last heartbeat time, errors, and other information.

## Flags

This table stores information for Flag values for experiments and pipelines synchronization. Flags can store key-value information to pass between nodes and control the execution flow (like mutexes).

You might want to manually modify this table in case of synchronization failures or issues (e.g., to continue experiment execution or provide data for executors to work with).