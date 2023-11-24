# Monitoring

For administrative purposes, the mediator service exposes a web page that provides administrative information. 

This page is available at the following URL: `http://<mediator_ip>:<mediator_port>/admin`. 

To access this page, you need to provide netUnicorn credentials of a user with `sudo` privileges.

Information on this page is divided into several sections:
- Active Experiments: a list of experiments that are not in "FINISHED" state.
- Locked Nodes: a list of nodes that are currently locked by some experiment.
- Active Compilations: a list of compilation processes that are currently running.