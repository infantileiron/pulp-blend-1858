from ..services import joint_service
from ..models.joint_plan import JointPlan
from ..models.joint_run import JointRun
from ..models.common import serialize
from .common import listing,require
def list_plans(db):return listing(db,JointPlan)
def detail_plan(db,ident):return serialize(require(db,JointPlan,ident))
def create_plan(db,body):return serialize(joint_service.create(db,body))
def list_runs(db):return listing(db,JointRun)
def detail_run(db,ident):return serialize(require(db,JointRun,ident))
def create_run(db,body):return serialize(joint_service.create_run(db,body))
