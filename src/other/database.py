from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# 定义 ORM 基类
Base = declarative_base()

class WxMsg(Base):
    __tablename__ = 'wx_msg'
    id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String)
    is_sender = Column(Boolean)  # 0/1, 也可用 Integer
    talker = Column(String)
    room_name = Column(String)
    msg = Column(String)
    src = Column(String)
    extra = Column(Text)
    CreateTime = Column(DateTime)

class WxUser(Base):
    __tablename__ = 'wx_user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    wxid = Column(String, unique=True, nullable=False)
    nickname = Column(String)
    remark = Column(String)
    account = Column(String)
    describe = Column(String)
    headImgUrl = Column(String)
    gender = Column(Integer)  # 1男2女，0未知
    signature = Column(String)
    country = Column(String)
    province = Column(String)
    city = Column(String)
    mobile = Column(String)

class WxUserChatroom(Base):
    __tablename__ = 'wx_user_chatroom'
    id = Column(Integer, primary_key=True, autoincrement=True)
    wxid = Column(String, nullable=False)         # 用户wxid
    room_name = Column(String, nullable=False)    # 聊天房id


# 初始化数据库函数
def init_database(db_path='sqlite:///wxdata.db'):
    # 创建数据库引擎
    engine = create_engine(db_path, echo=False)

    # 创建所有表（如果不存在）
    Base.metadata.create_all(engine)

    # 创建会话工厂
    Session = sessionmaker(bind=engine)
    
    return engine, Session
