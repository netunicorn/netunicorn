import utils.minion_handler
import utils.minion_pool

minions = utils.minion_pool.MinionPool().get()

for minion in minions:
    minion.runYoutubeExperiment()
