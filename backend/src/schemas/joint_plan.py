from pydantic import BaseModel,Field,field_validator,model_validator
from ..constants.enums import JOINT_MAX_ORDERS,JOINT_MAX_MATERIALS,JOINT_PACK_TONNES,JOINT_TIME_LIMIT_SECONDS
class JointOrderIn(BaseModel):
 order_id:str=Field(min_length=1,max_length=60)
 name:str=Field(min_length=1,max_length=180)
 tonnes:float=Field(gt=0,le=1000000,allow_inf_nan=False)
 spec_id:str=Field(min_length=1,max_length=36)
class JointPlanCreate(BaseModel):
 name:str=Field(min_length=2,max_length=180)
 dataset_id:str
 orders:list[JointOrderIn]=Field(min_length=1,max_length=JOINT_MAX_ORDERS)
 inventory:dict[str,float]
 time_limit_seconds:float=Field(default=JOINT_TIME_LIMIT_SECONDS,gt=0,le=JOINT_TIME_LIMIT_SECONDS)
 note:str=Field(default="",max_length=2000)
 @field_validator("inventory")
 @classmethod
 def inventory_values(cls,value):
  if len(value)>JOINT_MAX_MATERIALS:raise ValueError("原浆种类不得超过20种")
  for key,tonnes in value.items():
   if not key or len(key)>60:raise ValueError("原浆ID为空或过长")
   if not isinstance(tonnes,(int,float)) or tonnes!=tonnes or tonnes in (float("inf"),float("-inf")):raise ValueError(f"原浆{key}库存必须为有限数值")
   if tonnes<0 or tonnes>1e9:raise ValueError(f"原浆{key}库存须为0至1e9吨")
  return {key:float(tonnes) for key,tonnes in value.items()}
 @model_validator(mode="after")
 def unique_orders(self):
  ids=[order.order_id for order in self.orders]
  if len(ids)!=len(set(ids)):raise ValueError("订单编号不能重复")
  for order in self.orders:
   packs=order.tonnes/JOINT_PACK_TONNES
   if abs(packs-round(packs))>1e-9:raise ValueError(f"订单{order.order_id}吨数必须为{JOINT_PACK_TONNES}吨整包")
  return self
class JointRunCreate(BaseModel):
 plan_id:str
