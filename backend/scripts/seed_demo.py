import json
from sqlalchemy import select,func
from src.config.database import initialize,Session
from src.models import PulpDataset,QualitySpec,BlendScenario,BlendRun,FormulaReview,Report,User
from src.models.joint_plan import JointPlan
from src.models.joint_run import JointRun
from src.utils.security import hash_password
from src.services.run_service import compute

def make_materials():
 raw=[("P01","北杉针叶浆",5200,91,89,0,.65,3,1.5,0,200),("P02","南桉阔叶浆",3900,70,88,0,.7,3,2,0,160),("P03","高白竹浆",4200,74,91,0,.5,2.5,1.5,0,180),("P04","棉短绒浆",6500,98,94,0,.3,1.5,.8,0,250),("P05","净选回收浆",2600,56,74,.95,.6,4,3,.03,130),("P06","办公再生浆",3100,63,81,.88,.65,3,2,.04,150),("P07","未漂苇浆",2400,61,62,0,.25,4,3,0,120),("P08","机械木浆",2200,47,69,0,.25,5,3,0,100)]
 return [{"material_id":r[0],"name":r[1],"cost":r[2],"strength":r[3],"whiteness":r[4],"recycled":r[5],"min_share":0.,"max_share":r[6],"strength_width":r[7],"whiteness_width":r[8],"recycled_width":r[9],"cost_width":r[10]} for r in raw]

JOINT_SPECS=[
 ("demo-spec-coated","涂布文化纸模拟窗口",78,100,82,100,.20,.85,"较高强度与白度，回收纤维率封顶"),
 ("demo-spec-board","包装纸板模拟窗口",58,100,62,90,.55,1,"以回收纤维为主，白度上限较低"),
 ("demo-spec-tissue","生活用纸模拟窗口",64,100,88,100,0,.35,"高白度，回收纤维受限"),
 ("demo-spec-office","办公再生纸模拟窗口",66,100,78,95,.40,.90,"强度与白度折中，回收纤维为主"),
 ("demo-spec-carton","纸箱芯纸模拟窗口",62,100,70,100,.80,1,"强度62、白度70%、回收率80%同时触边；连续配方可行，0.5吨整包无解"),
]
JOINT_ORDERS=[("CY-2211","涂布文化纸",30.,"demo-spec-coated"),("BD-2211","包装纸板",18.,"demo-spec-board"),("TS-2211","生活用纸",10.,"demo-spec-tissue"),("OF-2211","办公再生纸",22.,"demo-spec-office")]
JOINT2_ORDERS=[("CX-2211","纸箱芯纸小单",2.,"demo-spec-carton")]
JOINT_INVENTORY={"P01":16.,"P02":20.,"P03":12.,"P04":4.,"P05":18.,"P06":20.,"P07":8.,"P08":12.}
JOINT_BASELINE_INVENTORY={"P01":40.,"P02":40.,"P03":40.,"P04":40.,"P05":40.,"P06":40.,"P07":40.,"P08":40.}
JOINT_SHORT_INVENTORY={"P01":12.,"P02":16.,"P03":9.,"P04":3.,"P05":12.,"P06":16.,"P07":6.,"P08":9.}

def seed_joint(db):
 from src.services.joint_service import compute as compute_joint
 for ident,name,smin,smax,wmin,wmax,rmin,rmax,note in JOINT_SPECS:
  if not db.get(QualitySpec,ident):db.add(QualitySpec(id=ident,name=name,strength_min=smin,strength_max=smax,whiteness_min=wmin,whiteness_max=wmax,recycled_min=rmin,recycled_max=rmax,description=note))
 db.commit()
 if not db.get(JointPlan,"demo-joint-plan"):db.add(JointPlan(id="demo-joint-plan",name="四纸种共享十一月原浆库存",dataset_id="demo-dataset",orders=[{"order_id":o,"name":n,"tonnes":t,"spec_id":s} for o,n,t,s in JOINT_ORDERS],inventory=dict(JOINT_INVENTORY),time_limit_seconds=30.,note="同一批八原浆，四个纸种共享库存；每纸种各原浆用量按0.5吨整包。"))
 if not db.get(JointPlan,"demo-joint-baseline"):db.add(JointPlan(id="demo-joint-baseline",name="四纸种库存充裕对照",dataset_id="demo-dataset",orders=[{"order_id":o,"name":n,"tonnes":t,"spec_id":s} for o,n,t,s in JOINT_ORDERS],inventory=dict(JOINT_BASELINE_INVENTORY),time_limit_seconds=30.,note="库存充裕，用于对照共享库存约束前后的成本。"))
 if not db.get(JointPlan,"demo-joint-short"):db.add(JointPlan(id="demo-joint-short",name="四纸种库存偏紧无解",dataset_id="demo-dataset",orders=[{"order_id":o,"name":n,"tonnes":t,"spec_id":s} for o,n,t,s in JOINT_ORDERS],inventory=dict(JOINT_SHORT_INVENTORY),time_limit_seconds=30.,note="同一批原浆库存收紧后，四单质量窗口与供给比例无法同时满足；用于验证连续冲突诊断与不伪造方案。"))
 if not db.get(JointPlan,"demo-joint-integer-gap"):db.add(JointPlan(id="demo-joint-integer-gap",name="纸箱芯纸整包无解示例",dataset_id="demo-dataset",orders=[{"order_id":o,"name":n,"tonnes":t,"spec_id":s} for o,n,t,s in JOINT2_ORDERS],inventory={"P01":100.,"P02":100.,"P03":100.,"P04":100.,"P05":100.,"P06":100.,"P07":100.,"P08":100.},time_limit_seconds=30.,note="连续配方可行，但0.5吨整包下回收率与白度无法同时满足，用于验证整包无解与不冒报。"))
 db.commit()
 if not db.get(JointRun,"demo-joint-run"):db.add(JointRun(id="demo-joint-run",plan_id="demo-joint-plan",status="queued",result={},error="",elapsed_seconds=0.));db.commit();compute_joint(db,"demo-joint-run")
 if not db.get(JointRun,"demo-joint-baseline-run"):db.add(JointRun(id="demo-joint-baseline-run",plan_id="demo-joint-baseline",status="queued",result={},error="",elapsed_seconds=0.));db.commit();compute_joint(db,"demo-joint-baseline-run")
 if not db.get(JointRun,"demo-joint-short-run"):db.add(JointRun(id="demo-joint-short-run",plan_id="demo-joint-short",status="queued",result={},error="",elapsed_seconds=0.));db.commit();compute_joint(db,"demo-joint-short-run")
 if not db.get(JointRun,"demo-joint-integer-gap-run"):db.add(JointRun(id="demo-joint-integer-gap-run",plan_id="demo-joint-integer-gap",status="queued",result={},error="",elapsed_seconds=0.));db.commit();compute_joint(db,"demo-joint-integer-gap-run")
 db.commit()
 return {JointPlan.__tablename__:db.scalar(select(func.count()).select_from(JointPlan)),JointRun.__tablename__:db.scalar(select(func.count()).select_from(JointRun))}

def seed():
 initialize()
 with Session() as db:
  for role in ["admin","analyst","viewer"]:
   email=role+"@pulp.demo"
   if not db.scalar(select(User).where(User.email==email)):db.add(User(id="user-"+role,email=email,role=role,password_hash=hash_password("PulpDemo2026!")))
  if not db.get(PulpDataset,"demo-dataset"):db.add(PulpDataset(id="demo-dataset",name="岑岳十一月原浆报价与检测",materials=make_materials(),description="8种模拟原浆；文件cenyue_pulp_202611.csv；属性仅按声明线性混合"))
  if not db.get(QualitySpec,"demo-spec"):db.add(QualitySpec(id="demo-spec",name="文化用纸模拟质量窗口",strength_min=70,strength_max=100,whiteness_min=80,whiteness_max=100,recycled_min=.25,recycled_max=1,description="强度指数、白度%、回收纤维率分别限定；不作工业认证"))
  db.commit()
  if not db.get(BlendScenario,"demo-scenario"):db.add(BlendScenario(id="demo-scenario",name="名义低成本与固定配方扰动",dataset_id="demo-dataset",spec_id="demo-spec",n_samples=400,seed=20261112,perturb_cost=True))
  db.commit()
  if not db.get(BlendRun,"demo-run"):db.add(BlendRun(id="demo-run",scenario_id="demo-scenario",status="queued",result={},error=""));db.commit();compute(db,"demo-run")
  if not db.get(FormulaReview,"demo-review"):db.add(FormulaReview(id="demo-review",run_id="demo-run",action="核查名义最优配方的活跃质量约束，并观察固定配方扰动通过数；线性混合和独立均匀误差仅为模拟假设。",state="approved",reviewer="admin@pulp.demo"))
  db.commit()
  if not db.get(Report,"demo-report"):db.add(Report(id="demo-report",review_id="demo-review",title="岑岳原浆配方稳健性底稿",snapshot={"result":db.get(BlendRun,"demo-run").result,"action":db.get(FormulaReview,"demo-review").action,"reviewer":"admin@pulp.demo"}))
  db.commit()
  result={cls.__tablename__:db.scalar(select(func.count()).select_from(cls)) for cls in [User,PulpDataset,QualitySpec,BlendScenario,BlendRun,FormulaReview,Report]}
  result.update(seed_joint(db))
  return result
if __name__=="__main__":print(json.dumps(seed(),ensure_ascii=False))
