from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..utils.auth import current,write_user
from ..schemas.joint_plan import JointPlanCreate,JointRunCreate
from ..controllers import joint_plan_controller as controller
router=APIRouter(prefix="/joint-plans",tags=["joint scheduling"])
@router.get("")
def plans(db=Depends(get_db),user=Depends(current)):return controller.list_plans(db)
@router.get("/runs")
def runs(db=Depends(get_db),user=Depends(current)):return controller.list_runs(db)
@router.get("/runs/{ident}")
def run(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail_run(db,ident)
@router.post("/runs",status_code=201)
def create_run(body:JointRunCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create_run(db,body)
@router.get("/{ident}")
def plan(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail_plan(db,ident)
@router.post("",status_code=201)
def create_plan(body:JointPlanCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create_plan(db,body)
