from pyvis.network import Network
from other.database import WxUser, WxMsg
import os
from datetime import datetime
import pickle
from copy import deepcopy
import json

class DataGraph:
    def __init__(self, Session, master):
        """
        初始化图，添加用户节点和交流边。
        """
        self.net = Network()
        self.master = master
        self.session = Session()
        
        # 检查是否已有存储的网络文件（改为只存储节点和边的数据）
        os.makedirs("data", exist_ok=True)
        nodes_filename = f"data/net_{self.master}_nodes.json"
        edges_filename = f"data/net_{self.master}_edges.json"
        if os.path.exists(nodes_filename) and os.path.exists(edges_filename):
            self.net = self.load_net_data(nodes_filename, edges_filename)
        else:
            # 添加用户节点与群聊节点
            self.add_node_to_net()

            # 添加交流边
            self.add_edges_to_net()

    def save_net_data(self, net, nodes_filename, edges_filename):
        # 保存节点
        with open(nodes_filename, "w") as f:
            json.dump([
                dict(n_id=node_id, **net.get_node(node_id)) for node_id in net.node_ids
            ], f)
        # 保存边
        with open(edges_filename, "w") as f:
            json.dump(list(net.edges), f)

    def load_net_data(self, nodes_filename, edges_filename):
        net = Network()
        # 读取节点
        with open(nodes_filename, "r") as f:
            nodes = json.load(f)
        for node in nodes:
            n_id = node.pop('n_id')
            net.add_node(n_id, **node)
        # 读取边
        with open(edges_filename, "r") as f:
            edges = json.load(f)
        for edge in edges:
            edge_args = edge.copy()
            if 'from' in edge_args:
                from_ = edge_args.pop('from')
            elif 'from_' in edge_args:
                from_ = edge_args.pop('from_')
            else:
                raise ValueError("Edge missing 'from' field")
            to = edge_args.pop('to')
            net.add_edge(from_, to, **edge_args)
        return net

    def add_node_to_net(self):
        def add_users_to_net():
            """
            从数据库读取用户数据，并添加到 pyvis 网络中，所有字段作为参数。
            """
            users = self.session.query(WxUser).filter(~WxUser.wxid.like('%@chatroom')).all()
            for user in users:
                label = f"{user.nickname or ''} ({user.wxid})"
                self.net.add_node(
                    user.wxid,
                    label=label,
                    group='user',
                    nickname=user.nickname,
                    remark=user.remark,
                    account=user.account,
                    gender=user.gender,
                    signature=user.signature,
                    country=user.country,
                    province=getattr(user, 'province', ''),
                    city=getattr(user, 'city', ''),
                    mobile=getattr(user, 'mobile', '')
                )

        def add_chatroom_to_net():
            """
            从数据库读取群聊数据，并添加到 pyvis 网络中，所有字段作为参数。
            """
            # 读取wx_msg表
            # 找到其中room_name字段中后缀为“@chatroom”的所有非重复字段，每一个非重复字段都是一个群聊
            chatrooms = (
                self.session.query(WxMsg.room_name)
                .filter(WxMsg.room_name.like('%@chatroom'))
                .distinct()
                .all()
            )
            # 添加群聊节点
            # 每个群聊节点的label为room_name，group为chatroom
            for (room_name,) in chatrooms:
                self.net.add_node(
                    room_name,
                    label=room_name,
                    group='chatroom'
                )
                
        # 添加用户节点
        add_users_to_net()
        # 添加群聊节点
        add_chatroom_to_net()


    def add_edges_to_net(self):
        """
        从数据库读取消息数据，并添加到 pyvis 网络中，所有字段作为参数。
        有两种消息数据，一种是私聊，一种是群聊
        """
        # 读取wx_msg表
        def create_private_edges():
            """
            创建私聊边
            """
            # 浏览一遍，对所有私聊关系建立权重，权重等于私聊次数
            private_edges = (
                self.session.query(WxMsg.talker, WxMsg.room_name)
                .filter(~WxMsg.room_name.like('%@chatroom'))
                .group_by(WxMsg.talker, WxMsg.room_name)
                .all()
            )
            # 检查room_name对应对应的用户wxid是否存在self.net中
            private_edges = [
                (talker, room_name) for talker, room_name in private_edges
                if talker in self.net.node_ids and room_name in self.net.node_ids
            ]
            # 对每一个私聊关系建立边
            # 如果talker是主节点，则边的方向为主节点->用户，否则为用户->主节点
            for talker, room_name in private_edges:
                weight = (
                    self.session.query(WxMsg)
                    .filter(WxMsg.talker == talker, WxMsg.room_name == room_name)
                    .count()
                )
                if talker == self.master:
                    self.net.add_edge(
                        self.master,
                        room_name,
                        weight=weight,
                        group='private_msg'
                    )
                else:
                    self.net.add_edge(
                        room_name,
                        self.master,
                        weight=weight,
                        group='private_msg'
                    )

        def create_chatroom_edges():
            """
            创建群聊边
            """
            # 浏览一遍，对所有私聊关系建立权重，权重等于私聊次数
            chatroom_edges = (
                self.session.query(WxMsg.talker, WxMsg.room_name)
                .filter(WxMsg.room_name.like('%@chatroom'))
                .group_by(WxMsg.talker, WxMsg.room_name)
                .all()
            )
            # 检查room_name对应对应的用户wxid是否存在self.net中
            chatroom_edges = [
                (talker, room_name) for talker, room_name in chatroom_edges
                if talker in self.net.node_ids and room_name in self.net.node_ids
            ]
            # 对每一个群聊关系建立边
            # 如果talker是主节点，则边的方向为主节点->用户，否则为用户->主节点
            for talker, room_name in chatroom_edges:
                weight = (
                    self.session.query(WxMsg)
                    .filter(WxMsg.talker == talker, WxMsg.room_name == room_name)
                    .count()
                )
                self.net.add_edge(
                    talker,
                    room_name,
                    weight=weight,
                    group='chatroom_msg'
                )
        
        create_private_edges()
        create_chatroom_edges()
    
    def get_send_msg_info(self):
        """
        发送消息信息
        - 总共发送信息数量
        - 发送信息最多的N人
        - 发送信息最多的N个群聊
        - 发送信息最多的N个时间段（不在这个函数）
        """
        ...

    def get_receive_msg_info(self):
        """
        接收消息次数
        """
        ...



    def visualize(self, output_path="graph.html", pattern='physics'):
        # 克隆已有的self.net到一个临时的net上
        temp_net = deepcopy(self.net)

        # 统计每个节点的所有相连边的权重和数量
        nodes_to_remove = []
        edges_to_remove = []

        for node_id in list(temp_net.node_ids):
            connected_edges = [e for e in temp_net.edges if e['from'] == node_id or e['to'] == node_id]
            total_weight = sum(e.get('weight', 1) for e in connected_edges)
            edge_count = len(connected_edges)
            if total_weight < 10 and edge_count < 3:
                nodes_to_remove.append(node_id)
                edges_to_remove.extend(connected_edges)

        # 删除节点和对应的边
        for node_id in nodes_to_remove:
            if node_id in temp_net.node_ids:
                temp_net.node_ids.remove(node_id)
                # 还需要从nodes列表中移除对应的node
                temp_net.nodes = [node for node in temp_net.nodes if node['id'] != node_id]
        for edge in edges_to_remove:
            if edge in temp_net.edges:
                temp_net.edges.remove(edge)

        # 删除孤立点（没有任何边的节点）
        isolated_nodes = [
            node_id for node_id in list(temp_net.node_ids)
            if not any(e['from'] == node_id or e['to'] == node_id for e in temp_net.edges)
        ]
        for node_id in isolated_nodes:
            temp_net.node_ids.remove(node_id)

        if pattern == 'physics':
            temp_net.show_buttons(filter_=['physics'])
        if pattern == 'force':
            temp_net.set_options("""
            {
                "physics": {
                    "barnesHut": {
                        "gravitationalConstant": -900,
                        "centralGravity": 0,
                        "springLength": 155,
                        "springConstant": 0.025,
                        "damping": 0.12,
                        "avoidOverlap": 0.15
                    },
                    "minVelocity": 0.75,
                    "timestep": 0.21
                }
            }
            """)
        # 保存self.net到本地data目录下，命名为"net+当前master id"
        os.makedirs("data", exist_ok=True)
        # 保存节点和边数据
        nodes_filename = f"data/net_{self.master}_nodes.json"
        edges_filename = f"data/net_{self.master}_edges.json"
        self.save_net_data(self.net, nodes_filename, edges_filename)
        temp_net.write_html(output_path)
        print(output_path)
