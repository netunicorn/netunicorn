from subprocess import Popen, PIPE
import salt.client


class MinionHandler:
    local = salt.client.LocalClient()
    project_path = "/home/ubuntu/active-measurements/"
    _git = "git --git-dir={0}.git --work-tree={0}".format(project_path)

    def __init__(self, minion_id):
        if not isinstance(minion_id, str):
            raise Exception(minion_id + " is not a string")

        self.minion_id = minion_id

    @staticmethod
    def lookupJob(job_id):
        process = Popen(['salt-run', 'jobs.lookup_jid', job_id], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        if stderr:
            raise Exception("stderr")
        return stdout

    def runCommand(self, command):
        job_id = self.local.cmd_async(self.minion_id, 'cmd.run', [command])
        print("running: ", command, " on:", self.minion_id, " job_id", job_id)
        return job_id

    def updateCode(self):
        print(MinionHandler.lookupJob(self.runCommand(self._git + " pull")))

    def runYoutubeExperiment(self):
        print(MinionHandler.lookupJob(self.runCommand('python3 {}ucsb/selenium_scripts/youtube_video.py'
                                                      .format(self.project_path))))
