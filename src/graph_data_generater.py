from knowledge_graph_builder import KGBuilder
from other.constant import NEO4J_URL, NEO4J_USER, NEO4J_PASS, output_json_example, master_user_id
import json
from other.preprocessing import DataPreprocessing
import time
from loguru import logger
import warnings
import os
from datetime import datetime
from llm import GeminiApiPOOL

import subprocess
import threading
from queue import Queue
from tqdm import tqdm

# 启动 caffeinate 保持唤醒
proc = subprocess.Popen(["caffeinate", "-dimsu"])

# 创建log文件夹（如果不存在）
log_dir = os.path.join(os.path.dirname(__file__), "log")
os.makedirs(log_dir, exist_ok=True)

# 日志文件名带时间戳
time_str = datetime.now().strftime("%Y%m%d")

# 配置Loguru日志文件，按类型分开，按大小切片
logger.add(os.path.join(log_dir, f"info_{time_str}.log"), level="INFO", rotation="10 MB", retention="10 days", encoding="utf-8")
logger.add(os.path.join(log_dir, f"warning_{time_str}.log"), level="WARNING", rotation="10 MB", retention="10 days", encoding="utf-8")
logger.add(os.path.join(log_dir, f"error_{time_str}.log"), level="ERROR", rotation="10 MB", retention="10 days", encoding="utf-8")
 
# 定义警告重定向到Loguru
def warning_to_loguru(message, category, filename, lineno, file=None, line=None):
    logger.warning(f"{category.__name__}: {message} ({filename}:{lineno})")

warnings.showwarning = warning_to_loguru

class WxidProcessor:
    def __init__(self, neo4j_config, llm_api_key_pool, master_user_info):
        self.neo4j_config = neo4j_config
        self.llm_api_key_pool = llm_api_key_pool
        self.master_user_info = master_user_info
        self.processed_wxids = set()
        self.queue = Queue()
        self.lock = threading.Lock()

    def process_wxid(self):
        while True:
            time.sleep(1)
            try:
                wxid, user_raw, messages = self.queue.get(timeout=1)  # 1秒超时
            except Queue.empty:
                break

            with self.lock:
                if wxid in self.processed_wxids:
                    self.queue.task_done()
                    continue

            try:
                users_raw = {
                    str(master_user_id): self.master_user_info,
                    str(wxid): user_raw,
                }

                kg = KGBuilder(
                    self.neo4j_config["url"],
                    self.neo4j_config["user"],
                    self.neo4j_config["password"],
                    self.llm_api_key_pool
                )
                users = kg.filter_user_info(users_raw)
                success = kg.process_and_push_pair(
                    messages=messages,
                    users=users
                )

                with self.lock:
                    if success:
                        self.processed_wxids.add(wxid)
                        logger.success(f"成功处理用户: {wxid}，还剩{self.queue.qsize()} 个待处理用户。")
                    else:
                        logger.error(f"处理失败: {wxid}")

            except Exception as e:
                logger.error(f"处理用户 {wxid} 时发生错误: {str(e)}")
            finally:
                self.queue.task_done()

if __name__ == "__main__":
    dp = DataPreprocessing(r"/Users/lige/data/DYKYRSC/wechat/json")
    master_user_info = dp.users.get(master_user_id, {})
    llm_api_key_pool = GeminiApiPOOL(r"/Users/lige/Desktop/api_key.xlsx")

    # Neo4j配置
    neo4j_config = {
        "url": NEO4J_URL,
        "user": NEO4J_USER,
        "password": NEO4J_PASS
    }

    # 创建处理器实例
    processor = WxidProcessor(neo4j_config, llm_api_key_pool, master_user_info)

    # 添加待处理的wxid到队列
    skipped_count = 0
    total_users = len(dp.wxid_list) - 1  # 减去master用户

    for wxid in dp.wxid_list:
        if wxid == master_user_id:
            continue

        user_raw = dp.users.get(wxid, {})
        messages = dp.msgs.get(wxid, [])

        if not user_raw or not messages:
            skipped_count += 1
            continue

        processor.queue.put((wxid, user_raw, messages))

    logger.info(f"总用户数: {total_users}, 跳过 {skipped_count} 个无数据用户, 待处理 {total_users - skipped_count} 个用户")

    # 创建并启动线程
    num_threads = 3  # 可以根据需要调整线程数
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=processor.process_wxid)
        t.daemon = True
        t.start()
        threads.append(t)

    # 等待队列处理完成
    processor.queue.join()


# TODO 如果有多个实体的话，将这些联系和节点强制绑定关系，不知道为什么，非用户实体总是默认和master绑定关系，而和其它user不绑定
# TODO 初步建立好图后，对图进行分析，重新建立关系，重新建立节点
# TODO 添加与时间的联系（考虑按月）
# TODO 所有联系都应该添加时间属性
# TODO 添加底层设置，个人经历补充，个人经历中的实体要提前创建并将id写入其中
# TODO kg导入报错导致的重试，应该把错误信息也传给llm
# TODO 单人详细聊天记录分析
# TODO nickname应该单独提出来到关系中？?
# TODO 开发一个简单的加入其他类型的节点联系的功能（插件功能）


proc.terminate()