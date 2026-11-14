from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from ..models.joint_plan import JointPlan
from ..models.joint_run import JointRun
from ..models.dataset import PulpDataset
from ..models.spec import QualitySpec
from ..constants.enums import PROPERTIES,JOINT_PACK_TONNES
from ..utils.queue import enqueue
from .joint_blend import solve,JointError

def _spec(spec_row):
 return {key+"_"+side:float(getattr(spec_row,key+"_"+side)) for key in PROPERTIES for side in ["min","max"]}

def create(db,body):
 data=db.get(PulpDataset,body.dataset_id)
 if data is None:raise HTTPException(422,"原浆批次不存在")
 if db.scalar(select(JointPlan).where(JointPlan.name==body.name)):raise HTTPException(409,"联合排产方案名称已存在")
 known={m["material_id"] for m in data.materials}
 unknown=sorted(key for key in body.inventory if key not in known)
 if unknown:raise HTTPException(422,"库存录入引用了不存在的原浆："+",".join(unknown))
 absent=sorted(m["material_id"] for m in data.materials if m["material_id"] not in body.inventory)
 if absent:raise HTTPException(422,"请为每种原浆录入库存（含0），尚缺："+",".join(absent))
 for order in body.orders:
  if db.get(QualitySpec,order.spec_id) is None:raise HTTPException(422,f"订单{order.order_id}的质量窗口不存在")
  if abs(order.tonnes/JOINT_PACK_TONNES-round(order.tonnes/JOINT_PACK_TONNES))>1e-9:raise HTTPException(422,f"订单{order.order_id}吨数必须为{JOINT_PACK_TONNES}吨整包")
 row=JointPlan(id=str(uuid4()),**body.model_dump());db.add(row);db.commit();return row

def payload(db,plan):
 data=db.get(PulpDataset,plan.dataset_id)
 if data is None:raise HTTPException(409,"方案关联的原浆批次已不存在")
 inventory={m["material_id"]:0. for m in data.materials}
 for key,value in plan.inventory.items():inventory[key]=float(value)
 orders=[]
 for item in plan.orders:
  spec_row=db.get(QualitySpec,item["spec_id"])
  if spec_row is None:raise HTTPException(409,f"质量窗口{item['spec_id']}已不存在")
  orders.append({"order_id":item["order_id"],"name":item["name"],"tonnes":float(item["tonnes"]),"spec_id":item["spec_id"],"spec_name":spec_row.name,"spec":_spec(spec_row)})
 return data.materials,inventory,orders

def create_run(db,body):
 plan=db.get(JointPlan,body.plan_id)
 if plan is None:raise HTTPException(422,"联合排产方案不存在")
 if not 1<=len(plan.orders)<=8:raise HTTPException(422,"订单须为1至8个")
 row=JointRun(id=str(uuid4()),plan_id=plan.id,status="queued",result={},error="",elapsed_seconds=0.);db.add(row);db.commit()
 try:enqueue(row.id,"joint")
 except Exception:
  row.status="failed";row.error="Redis队列不可用，请稍后重试";db.commit();raise HTTPException(503,row.error)
 return row

def compute(db,run_id):
 row=db.get(JointRun,run_id)
 if row is None or row.status not in ["queued","running"]:return
 row.status="running";db.commit()
 try:
  plan=db.get(JointPlan,row.plan_id)
  if plan is None:raise JointError("联合排产方案不存在")
  materials,inventory,orders=payload(db,plan)
  result=solve(orders,materials,inventory,plan.time_limit_seconds)
  result.update({"plan_name":plan.name,"dataset_name":db.get(PulpDataset,plan.dataset_id).name,"note":plan.note})
  row.result=result;row.elapsed_seconds=float(result.get("elapsed_seconds") or 0.)
  status={"optimal":"completed","timeout":"completed","infeasible":"infeasible","undetermined":"undetermined","failed":"failed"}
  row.status=status.get(result["status"],"failed")
  if not result["feasible"]:row.error=result.get("reason") or ""
 except JointError as e:row.status="failed";row.error=str(e)[:1000]
 except Exception as e:row.status="failed";row.error=str(e)[:1000]
 db.commit()
