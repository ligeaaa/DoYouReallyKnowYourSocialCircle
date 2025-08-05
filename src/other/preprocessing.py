import os
import json
from other.database import WxMsg, WxUser, WxUserChatroom



class DataPreprocessing:
    """
    数据预处理类，用于读取指定文件夹下的所有文件。
    """

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.file_paths = self.read_all_files_in_folder()
        self.users, self.msgs = self.read_users_and_msgs(self.file_paths)
        self.wxid_list = [k for k in self.users.keys() if isinstance(k, str) and k.startswith("wxid_")]

    def read_all_files_in_folder(self):
        """
        读取指定文件夹下的所有文件（包括子文件夹中的文件），返回文件的完整路径列表。
        先读取一级子目录，判断是否跳过，再递归读取。
        """
        file_paths = []
        for direction in os.listdir(self.folder_path):
            dir_path = os.path.join(self.folder_path, direction)
            if not os.path.isdir(dir_path):
                continue
            if direction.startswith("gh_") or direction.startswith("@") or direction.endswith("@openim"):
                continue
            for root, _, files in os.walk(dir_path):
                file_paths += [os.path.join(root, file) for file in files]
        return file_paths

    def read_users_and_msgs(self, paths, encoding="utf-8"):
        """
        读取所有文件，将 users.json 文件内容存入 users，其余文件内容存入 msgs。
        返回 (users, msgs) 两个字典。
        """
        users = {}
        msgs = {}
        for path in paths:
            try:
                with open(path, "r", encoding=encoding) as f:
                    id = os.path.basename(os.path.dirname(path))
                    data = json.load(f)
                    if os.path.basename(path) == "users.json":
                        users[id] = data
                    else:
                        msgs[id] = data
            except Exception:
                if os.path.basename(path) == "users.json":
                    users = None
                else:
                    msgs[path] = None

        def process_users(raw_users):
            """
            从self.users中提取所有唯一的用户信息（以wxid为唯一标识）。
            返回一个以wxid为key，用户信息为value的字典。
            """
            processed_users = {}
            for user_dict in raw_users.values():
                # user_dict 可能是一个包含多个用户的dict
                for wxid, user_info in user_dict.items():
                    if wxid not in processed_users:
                        processed_users[wxid] = user_info
            return processed_users
        
        def process_msgs(raw_msgs):
            ...
        
        users = process_users(users)

        return users, msgs
    
    def store_data_to_sqlite(self, engine, Session):
        """
        将预处理后的数据存储到SQLite数据库中。
        需要实现具体的存储逻辑。
        """
        from sqlalchemy.exc import IntegrityError
        import datetime

        with Session() as session:
            # 存储用户数据
            for wxid, user_info in self.users.items():
                # 确保 user_info 是 dict
                if not isinstance(user_info, dict):
                    continue
                extra = user_info.get("ExtraBuf", {}) or {}
                wx_user = WxUser(
                    wxid=wxid,
                    nickname=user_info.get("nickname"),
                    remark=user_info.get("remark"),
                    account=user_info.get("account"),
                    describe=user_info.get("describe"),
                    headImgUrl=user_info.get("headImgUrl"),
                    gender=extra.get("性别[1男2女]", 0),
                    signature=extra.get("个性签名", ""),
                    country=extra.get("国", ""),
                    province=extra.get("省", ""),
                    city=extra.get("市", ""),
                    mobile=extra.get("手机号", ""),
                )
                session.add(wx_user)

            # 存储消息数据
            for msg_list in self.msgs.values():
                for msg in msg_list:
                    # 解析时间
                    create_time = msg.get("CreateTime")
                    try:
                        if create_time:
                            create_time = datetime.datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
                        else:
                            create_time = None
                    except Exception:
                        create_time = None


                    def safe_json(val):
                        if isinstance(val, (dict, list)):
                            return json.dumps(val, ensure_ascii=False)
                        return val

                    wx_msg = WxMsg(
                        type_name=msg.get("type_name"),
                        is_sender=bool(msg.get("is_sender", 0)),
                        talker=msg.get("talker"),
                        room_name=msg.get("room_name"),
                        msg=safe_json(msg.get("msg")),
                        src=safe_json(msg.get("src")),
                        extra=safe_json(msg.get("extra", {})),
                        CreateTime=create_time
                    )
                    session.add(wx_msg)

            try:
                session.commit()
            except IntegrityError as e:
                session.rollback()
                print("数据写入时发生唯一性冲突，部分数据未写入。")
                print("详细错误信息：", e.orig)


# 示例用法
if __name__ == "__main__":
    dp = DataPreprocessing(r"/Users/lige/data/DYKYRSC/wechat/json")
    print("users:", type(dp.users), len(dp.users) if dp.users else 0)
    print("msgs:", type(dp.msgs), len(dp.msgs))
