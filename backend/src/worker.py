import time,logging
from pathlib import Path
from .config.database import Session
from .utils.queue import client,QUEUE,JOINT_QUEUE
from .services.run_service import compute
from .services.joint_service import compute as compute_joint
heartbeat=Path("/artifacts/worker-heartbeat")
while True:
 try:
  heartbeat.touch()
  item=client().blpop([QUEUE,JOINT_QUEUE],timeout=2)
  if item:
   queue,ident=item
   with Session() as db:
    if queue==JOINT_QUEUE:compute_joint(db,ident)
    else:compute(db,ident)
 except Exception:logging.exception("Worker error");time.sleep(2)
