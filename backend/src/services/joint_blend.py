import math
import time
import numpy as np
from scipy.optimize import milp,linprog,LinearConstraint,Bounds
from ..constants.enums import PROPERTIES,CONSTRAINT_TOLERANCE,JOINT_PACK_TONNES,JOINT_TIME_LIMIT_SECONDS

class JointError(ValueError):pass

def packs_for(tonnes):
 value=tonnes/JOINT_PACK_TONNES;nearest=round(value)
 if nearest<0 or abs(value-nearest)>1e-9:raise JointError(f"订单吨数{tonnes}不是{JOINT_PACK_TONNES}吨整包")
 return int(nearest)

def _validate(orders,materials,inventory,time_limit):
 if not 1<=len(orders)<=8:raise JointError("订单须为1至8个")
 if not 2<=len(materials)<=20:raise JointError("原浆须为2至20种")
 if not 0<time_limit<=JOINT_TIME_LIMIT_SECONDS:raise JointError("计算时限须在0至30秒")
 ids={m["material_id"] for m in materials};seen=set()
 for m in materials:
  if not math.isfinite(m["cost"]) or m["cost"]<=0:raise JointError("原浆成本无效")
  if not 0<=m["min_share"]<=m["max_share"]<=1:raise JointError("原浆供给比例无效")
 for key,value in inventory.items():
  if key not in ids:raise JointError(f"库存录入引用了不存在的原浆{key}")
  if not math.isfinite(value) or value<0:raise JointError(f"原浆{key}库存无效")
 for order in orders:
  if order["order_id"] in seen:raise JointError("订单编号重复")
  seen.add(order["order_id"]);packs_for(order["tonnes"])
  for key in PROPERTIES:
   if not 0<=order["spec"][key+"_min"]<=order["spec"][key+"_max"]:raise JointError(f"订单{order['order_id']}的{key}质量界限无效")

def _integer(orders,materials,inventory):
 count=len(orders)*len(materials);packs=[packs_for(order["tonnes"]) for order in orders]
 objective=np.array([JOINT_PACK_TONNES*m["cost"] for _ in orders for m in materials],dtype=float)
 eq=np.zeros((len(orders),count));eq_rhs=np.array(packs,dtype=float)
 upper=[];lower=[]
 for j in range(len(orders)):
  eq[j,j*len(materials):(j+1)*len(materials)]=1.
  for m in materials:lower.append(m["min_share"]*packs[j]);upper.append(m["max_share"]*packs[j])
 A=[];lb=[];ub=[]
 for i,m in enumerate(materials):
  row=np.zeros(count)
  for j in range(len(orders)):row[j*len(materials)+i]=1.
  A.append(row);lb.append(0.);ub.append(inventory.get(m["material_id"],0.)/JOINT_PACK_TONNES)
 for key in PROPERTIES:
  values=np.array([m[key] for m in materials],dtype=float)
  for j,order in enumerate(orders):
   row=np.zeros(count);row[j*len(materials):(j+1)*len(materials)]=values
   A.append(row);lb.append(order["spec"][key+"_min"]*packs[j]);ub.append(order["spec"][key+"_max"]*packs[j])
 return objective,eq,eq_rhs,np.vstack(A),np.array(lb,dtype=float),np.array(ub,dtype=float),np.array(lower,dtype=float),np.array(upper,dtype=float),packs

def _build(orders,materials,packs,solutions,inventory_input):
 lines=[];total=0.;used=np.zeros(len(materials))
 for j,order in enumerate(orders):
  entry={"index":j,"order_id":order["order_id"],"name":order["name"],"tonnes":order["tonnes"],"packs":packs[j],"spec_name":order.get("spec_name",""),"lines":[],"qualities":[],"share_sum":0.,"cost":0.}
  for i,m in enumerate(materials):
   count=int(solutions[j*len(materials)+i]);tonnes=count*JOINT_PACK_TONNES;share=count/packs[j] if packs[j] else 0.
   entry["lines"].append({"material_id":m["material_id"],"name":m["name"],"packs":count,"tonnes":tonnes,"share":share,"unit_cost":m["cost"],"line_cost":tonnes*m["cost"],"min_share":m["min_share"],"max_share":m["max_share"],"lower_slack":share-m["min_share"],"upper_slack":m["max_share"]-share})
   entry["share_sum"]+=share;entry["cost"]+=tonnes*m["cost"];used[i]+=tonnes
  total+=entry["cost"]
  for key in PROPERTIES:
   value=sum(line["tonnes"]*materials[i][key] for i,line in enumerate(entry["lines"]))/order["tonnes"]
   entry["qualities"].append({"property":key,"value":value,"minimum":order["spec"][key+"_min"],"maximum":order["spec"][key+"_max"],"lower_slack":value-order["spec"][key+"_min"],"upper_slack":order["spec"][key+"_max"]-value})
  lines.append(entry)
 inventory=[];remaining_total=0.
 for i,m in enumerate(materials):
  available=float(inventory_input.get(m["material_id"],0.));remaining=available-used[i];remaining_total+=remaining
  inventory.append({"material_id":m["material_id"],"name":m["name"],"inventory_tonnes":available,"used_tonnes":float(used[i]),"used_packs":int(round(used[i]/JOINT_PACK_TONNES)),"remaining_tonnes":float(remaining),"unit_cost":m["cost"]})
 failures=[]
 for entry in lines:
  order=entry
  if sum(line["packs"] for line in order["lines"])!=order["packs"]:failures.append(f"订单{order['order_id']}整包数之和不等于{order['packs']}")
  if abs(order["share_sum"]-1)>CONSTRAINT_TOLERANCE:failures.append(f"订单{order['order_id']}比例和不为1")
  for line in order["lines"]:
   if not isinstance(line["packs"],int) or line["packs"]<0:failures.append(f"订单{order['order_id']}原浆{line['material_id']}整包数非法")
   if line["share"]<line["min_share"]-CONSTRAINT_TOLERANCE or line["share"]>line["max_share"]+CONSTRAINT_TOLERANCE:failures.append(f"订单{order['order_id']}原浆{line['material_id']}供给比例越界")
  for quality in order["qualities"]:
   if quality["value"]<quality["minimum"]-CONSTRAINT_TOLERANCE or quality["value"]>quality["maximum"]+CONSTRAINT_TOLERANCE:failures.append(f"订单{order['order_id']}的{quality['property']}越界")
 for i,m in enumerate(materials):
  if used[i]>inventory_input.get(m["material_id"],0.)+CONSTRAINT_TOLERANCE:failures.append(f"原浆{m['material_id']}用量超过库存")
 return lines,inventory,float(total),float(remaining_total),{"passed":not failures,"failures":failures,"tolerance":CONSTRAINT_TOLERANCE,"pack_tonnes":JOINT_PACK_TONNES,"checked":["整包整数","每单整包数之和","供给比例上下界","三个质量窗口","共享库存结余"]}

def _totals(orders,materials,inventory_input):
 return {"demand_tonnes":float(sum(order["tonnes"] for order in orders)),"inventory_tonnes":float(sum(float(inventory_input.get(m["material_id"],0.)) for m in materials))}

def _shortfalls(orders,materials,inventory_input):
 entries=[]
 for m in materials:
  available=float(inventory_input.get(m["material_id"],0.));required=sum(order["tonnes"]*m["min_share"] for order in orders)
  maximum=sum(order["tonnes"]*m["max_share"] for order in orders)
  if required>available+CONSTRAINT_TOLERANCE:entries.append({"material_id":m["material_id"],"name":m["name"],"inventory_tonnes":available,"minimum_required_tonnes":required,"shortfall_tonnes":required-available,"maximum_allowed_tonnes":maximum})
 return entries

def _per_order(orders,materials,inventory_input):
 checks=[]
 for order in orders:
  try:
   objective,eq,eq_rhs,A,lb,ub,lower,upper,packs=_integer([order],materials,inventory_input)
   lp=_relaxation(objective,eq,eq_rhs,A,lb,ub,lower,upper,.25)
   alone=True if lp.status==0 and np.isfinite(lp.fun) else (False if lp.status==2 else None)
  except Exception:alone=None
  checks.append({"order_id":order["order_id"],"name":order["name"],"tonnes":order["tonnes"],"alone_continuous_feasible":alone})
 return checks

def _order_bounds(orders,materials):
 result=[]
 for order in orders:
  result.append({"order_id":order["order_id"],"name":order["name"],"tonnes":order["tonnes"],"packs":packs_for(order["tonnes"]),"spec_name":order.get("spec_name",""),"spec":{key:{"min":order["spec"][key+"_min"],"max":order["spec"][key+"_max"]} for key in PROPERTIES}})
 return result

def _reconstruct(x,lower,upper):
 candidate=np.asarray(x,dtype=float)
 if not np.isfinite(candidate).all():return None
 rounded=np.rint(candidate)
 if np.abs(candidate-rounded).max()>1e-5:return None
 if (rounded<lower-1e-6).any() or (rounded>upper+1e-6).any():return None
 return rounded.astype(int)

def _relaxation(objective,eq,eq_rhs,A,lb,ub,lower,upper,time_limit):
 A_ub=np.vstack([A,-A]);b_ub=np.concatenate([ub,-lb])
 return linprog(objective,A_ub=A_ub,b_ub=b_ub,A_eq=eq,b_eq=eq_rhs,bounds=list(zip(lower,upper)),method="highs",options={"time_limit":max(.01,time_limit)})

def solve(orders,materials,inventory_input,time_limit=JOINT_TIME_LIMIT_SECONDS):
 _validate(orders,materials,inventory_input,time_limit);start=time.monotonic();deadline=start+time_limit
 totals=_totals(orders,materials,inventory_input);shortfalls=_shortfalls(orders,materials,inventory_input);order_bounds=_order_bounds(orders,materials);per_order=None
 objective,eq,eq_rhs,A,lb,ub,lower,upper,packs=_integer(orders,materials,inventory_input)
 lp=_relaxation(objective,eq,eq_rhs,A,lb,ub,lower,upper,time_limit*.25)
 if lp.status==2:
  per_order=_per_order(orders,materials,inventory_input)
  return {"status":"infeasible","feasible":False,"reason":"共享库存、供给比例与各订单质量窗口在连续配方下已冲突：无需整包即无可行方案","diagnosis":{"continuous_feasible":False,"pack_feasible":False,"totals":totals,"inventory_shortfalls":shortfalls,"orders":order_bounds,"per_order":per_order},"orders_input":order_bounds,"lower_bound":None,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":{"stage":"integer-relaxation","status":int(lp.status),"message":lp.message},"orders":[],"inventory":[],"total_cost":None}
 if not lp.success or not np.isfinite(lp.fun):return {"status":"undetermined","feasible":False,"reason":"整数松弛未给出有限下界，不能据此判断无解","diagnosis":{"continuous_feasible":None,"pack_feasible":None,"totals":totals,"orders":order_bounds},"orders_input":order_bounds,"lower_bound":None,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":{"stage":"integer-relaxation","status":int(lp.status),"message":lp.message},"orders":[],"inventory":[],"total_cost":None,"continuous_feasible":lp.status==0}
 lower_bound=float(lp.fun);remaining=deadline-time.monotonic()
 if remaining<.05:return {"status":"undetermined","feasible":False,"reason":"已到计算时限，整包搜索尚未开始；不下无解结论","diagnosis":{"continuous_feasible":True,"pack_feasible":None,"totals":totals,"orders":order_bounds},"orders_input":order_bounds,"lower_bound":lower_bound,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":{"stage":"integer-relaxation","status":int(lp.status),"message":lp.message},"orders":[],"inventory":[],"total_cost":None,"continuous_feasible":True}
 result=milp(objective,integrality=np.ones(len(objective)),bounds=Bounds(lower,upper),constraints=[LinearConstraint(eq,eq_rhs,eq_rhs),LinearConstraint(A,lb,ub)],options={"time_limit":max(.01,remaining-.05),"mip_rel_gap":0.0,"presolve":True})
 solver={"stage":"integer","status":int(result.status),"message":result.message,"node_count":int(getattr(result,"mip_node_count",None) or 0),"mip_gap":None,"dual_bound":None,"integer_relaxation_lower_bound":lower_bound}
 if result.status==2:
  per_order=_per_order(orders,materials,inventory_input)
  return {"status":"infeasible","feasible":False,"reason":"连续配方可行，但0.5吨整包无法同时满足全部订单；半吨整包整数模型无解","diagnosis":{"continuous_feasible":True,"pack_feasible":False,"totals":totals,"inventory_shortfalls":shortfalls,"orders":order_bounds,"per_order":per_order},"orders_input":order_bounds,"lower_bound":None,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":solver,"orders":[],"inventory":[],"total_cost":None,"continuous_feasible":True}
 dual=getattr(result,"mip_dual_bound",None)
 if dual is not None and np.isfinite(dual):lower_bound=max(lower_bound,float(dual));solver["dual_bound"]=float(dual)
 incumbent=_reconstruct(result.x,lower,upper)
 if incumbent is None:
  reason="已到计算时限，未找到可核验的整包方案；不下无解结论" if result.status==1 else "整数求解未给出可核验整包方案；不下无解结论"
  return {"status":"undetermined" if result.status==1 else "failed","feasible":False,"reason":reason,"diagnosis":{"continuous_feasible":True,"pack_feasible":None,"totals":totals,"orders":order_bounds},"orders_input":order_bounds,"lower_bound":lower_bound,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":solver,"orders":[],"inventory":[],"total_cost":None,"continuous_feasible":True}
 lines,inventory,total,remaining_total,verification=_build(orders,materials,packs,incumbent,inventory_input)
 if not verification["passed"]:return {"status":"failed","feasible":False,"reason":"整数方案未通过独立约束核验，不作为可行方案，也不判无解","lower_bound":lower_bound,"gap":None,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":solver,"verification":verification,"orders":[],"inventory":[],"total_cost":None}
 if result.status==0:
  lower_bound=float(result.fun);status="optimal";gap=0.0
 else:
  lower_bound=min(lower_bound,total)
  solver["mip_gap"]=(total-lower_bound)/abs(total) if total else None;status="timeout";gap=max(0.,(total-lower_bound)/abs(total)) if total else 0.
 return {"status":status,"feasible":True,"reason":"半吨整包整数最优解，已通过独立约束核验" if status=="optimal" else "已到计算时限，以下为独立核验通过的可行整包方案；附成本下界与差距","lower_bound":lower_bound,"gap":gap,"time_limit_seconds":time_limit,"elapsed_seconds":time.monotonic()-start,"solver":solver,"total_cost":total,"remaining_tonnes":remaining_total,"orders":lines,"inventory":inventory,"verification":verification,"continuous_feasible":True,"cost_unit":"CNY","pack_tonnes":JOINT_PACK_TONNES,"comparison_tolerance":CONSTRAINT_TOLERANCE,"diagnosis":{"continuous_feasible":True,"pack_feasible":True,"optimality_proven":status=="optimal","totals":totals,"inventory_shortfalls":shortfalls,"orders":order_bounds},"orders_input":order_bounds,"gap_definition":"(可行方案总成本 − 成本下界)/可行方案总成本；下界取整数松弛与整数求解对偶界的较大者，是全部订单同时满足时总成本不可能低于的值。","assumption":"每纸种各原浆用量按0.5吨整包取整数包；沿用各原浆供给比例上下界与每订单质量窗口；全部订单共享同一批原浆库存，线性加权混合仅为本模拟模型假设。"}
