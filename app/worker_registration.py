"""Restore essential registry metadata after Redis expiry/VM sleep."""
from rq import SpawnWorker


class RegistrationMixin:
    def heartbeat(self, timeout=None, pipeline=None):
        # RQ heartbeat alone recreates only last_heartbeat after a hash expires.
        # Repair queues and identity before extending TTL, without deleting keys.
        conn=pipeline if pipeline is not None else self.connection
        conn.hset(self.key,mapping={'queues':','.join(self.queue_names()),
                                  'name':self.name,'hostname':self.hostname,'pid':self.pid})
        return super().heartbeat(timeout=timeout,pipeline=pipeline)


class ReliableSpawnWorker(RegistrationMixin,SpawnWorker):
    pass
