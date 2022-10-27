from unicorn.base.experiment import Experiment
from unicorn.base.pipeline import Pipeline
from unicorn.client.remote import RemoteClient
from unicorn.library.qoe_youtube import (
    StartQoECollectionServer,
    StopQoECollectionServer,
    WatchYouTubeVideo,
)

MININET = True
if MININET:
    host1 = "h1"
    host2 = "h2"
    server = "localhost"
else:
    host1 = "raspi-dc:a6:32:d7:6e:64"
    host2 = "raspi-e4:5f:01:2e:1e:55"
    server = "netunicorn.cs.ucsb.edu"

client = RemoteClient(server, 26511, "kell", "kell")
minions = client.get_minion_pool()
a, b = [x for x in minions if x.name in {host1, host2}]
dmap = Experiment()
pipeline1 = (
    Pipeline()
    .then(StartQoECollectionServer(port=34546))
    .then(
        WatchYouTubeVideo(
            "https://www.youtube.com/watch?v=ZO8V8Vb-Jbk", 10, qoe_server_port=34546
        )
    )
    .then(StopQoECollectionServer())
)
pipeline2 = (
    Pipeline()
    .then(StartQoECollectionServer(port=34547))  # to let it work in case of mininet
    .then(
        WatchYouTubeVideo(
            "https://www.youtube.com/watch?v=ZO8V8Vb-Jbk", 10, qoe_server_port=34547
        )
    )
    .then(StopQoECollectionServer())
)
pipeline1.environment_definition.commands = []
pipeline2.environment_definition.commands = []

dmap.append(a, pipeline1)
dmap.append(b, pipeline2)

client.prepare_experiment(dmap, "test")
client.get_experiment_status("test")
client.start_execution("test")
