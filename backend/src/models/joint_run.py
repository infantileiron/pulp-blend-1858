from sqlalchemy import String,Text,JSON,ForeignKey,Double
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class JointRun(RecordMixin,Base):
 __tablename__="joint_runs"
 plan_id:Mapped[str]=mapped_column(ForeignKey("joint_plans.id"))
 status:Mapped[str]=mapped_column(String(20),default="queued")
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default="")
 elapsed_seconds:Mapped[float]=mapped_column(Double,default=0.)
