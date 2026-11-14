from redis import Redis
from ..config.settings import REDIS_URL
QUEUE="pulp-blend:runs"
JOINT_QUEUE="pulp-blend:joint-runs"
def client(): return Redis.from_url(REDIS_URL,decode_responses=True)
def enqueue(run_id,kind="blend"): client().rpush(JOINT_QUEUE if kind=="joint" else QUEUE,run_id)
