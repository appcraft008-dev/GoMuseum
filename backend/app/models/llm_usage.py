"""LLM 用量记账(成本可观测性,backlog LLM成本工程①)。
day×channel×model 一行累加;日志随部署 recreate 抹掉故必须落库。"""

from sqlalchemy import BigInteger, Column, Date, Integer, String

from app.core.database import Base


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    day = Column(Date, primary_key=True)
    channel = Column(
        String(32), primary_key=True
    )  # generate|gate|translate|qa|names|intro|tts|misc
    model = Column(String(64), primary_key=True)
    calls = Column(Integer, nullable=False, default=0)
    tokens_in = Column(BigInteger, nullable=False, default=0)  # tts=输入字符数
    tokens_out = Column(BigInteger, nullable=False, default=0)
