from other.database import init_database
from other.preprocessing import DataPreprocessing
from other.graph import DataGraph

def init_data():
    # 初始化数据库
    engine, Session = init_database()

    # 创建数据预处理实例
    dp = DataPreprocessing(r"/Users/lige/data/DYKYRSC/wechat/json")
    # 存储数据到sqlite
    dp.store_data_to_sqlite(engine, Session)

def main():
    # 从聊天记录中构建一个图（Graph），节点为人，边为交流联系。
    # 考虑是否有异质节点（例如将群聊也当作是一个节点）    
    engine, Session = init_database()

    master = "wxid_yner05jjwmry11"  # 主节点，通常是自己
    G = DataGraph(Session, master)
    G.visualize(pattern="force")


if __name__ == "__main__":
    # init_data()
    main()
    # TODO 新增算法处理类，传入DataGraph，其中有多个算法方法，输出各种参数
    # TODO delete chatrooms from database WXuser

