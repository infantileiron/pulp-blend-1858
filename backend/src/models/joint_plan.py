from sqlalchemy import String,Text,JSON,ForeignKey,Double
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class JointPlan(RecordMixin,Base):
 __tablename__="joint_plans"
 name:Mapped[str]=mapped_column(String(180),unique=True)
 dataset_id:Mapped[str]=mapped_column(ForeignKey("datasets.id"))
 orders:Mapped[list]=mapped_column(JSON)
 inventory:Mapped[dict]=mapped_column(JSON)
 time_limit_seconds:Mapped[float]=mapped_column(Double,default=30.)
 note:Mapped[str]=mapped_column(Text,default="")
