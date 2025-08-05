from typing import List
from other.graph import DataGraph

class GraphAnalyzer:
    def __init__(self, data_graph_list: List[DataGraph]):
        self.data_graph = data_graph
        self.master_list = [] # TODO 添加函数一键获取
        self.combine_data_graph() # TODO

    def analyze_top_n_contacts(self, n=10):
        # 示例：分析联系最多的N个人
        pass

    def analyze_communities(self):
        # 示例：社区发现算法
        # TODO 把毕设内容引进来，减少工作量（？）
        pass

    # 你可以继续添加其它分析方法