
from asopimx.tools import Singleton
import sched

class Scheduler(sched.scheduler, metaclass=Singleton):
    def run(self, blocking=False):
        return super(Scheduler, self).run(blocking)
