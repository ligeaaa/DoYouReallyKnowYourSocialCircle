import json
import re
import jieba
from collections import Counter, defaultdict
from py2neo import Graph, Node, Relationship
from other.constant import NEO4J_URL, NEO4J_USER, NEO4J_PASS, output_json_example
from loguru import logger
from llm import build_prompt, call_llm
import datetime

class KGBuilder:
    def __init__(self, neo4j_url, neo4j_user, neo4j_pass, llm_api_key_pool):
        self.graph = Graph(neo4j_url, auth=(neo4j_user, neo4j_pass))
        self.llm_api_key_pool = llm_api_key_pool

    @staticmethod
    def filter_user_info(user_dict):
        keys = [
            "wxid", "nickname", "remark", "account",
            "LabelIDList"
        ]
        extra_keys = [
            "性别[1男2女]", "个性签名", "国", "省", "市", "手机号"
        ]
        filtered = {}
        for wxid, info in user_dict.items():
            new_info = {k: info.get(k, "") for k in keys}
            extra = info.get("ExtraBuf", {})
            for ek in extra_keys:
                new_info[ek] = extra.get(ek, "")
            filtered[wxid] = new_info
        return filtered

    @staticmethod
    def clean_msg(raw_msg: str) -> str:
        msg = raw_msg.replace("我通过了你的朋友验证请求，现在我们可以开始聊天了", "").strip()
        return msg

    @staticmethod
    def preprocess_messages(messages):
        clean_data = []
        for m in messages:
            if m['type_name'] == '文本' and m['msg']:
                m['clean_msg'] = KGBuilder.clean_msg(m['msg'])
                clean_data.append(m)
        return clean_data

    @staticmethod
    def extract_keywords_and_stats(messages_clean):
        """
        Extracts keywords and statistical information from a list of cleaned message dictionaries.

        Args:
            messages_clean (list): A list of dictionaries, each representing a message with at least
                'CreateTime' (str, format 'YYYY-MM-DD ...') and 'clean_msg' (str, cleaned message text).

        Returns:
            dict: A dictionary containing:
                - "all_words" (list): All valid words extracted from messages.
                - "word_counter" (Counter): Frequency count of all valid words.
                - "day_counter" (Counter): Count of messages per day (key: 'YYYY-MM-DD').
                - "month_counter" (Counter): Count of messages per month (key: 'YYYY-MM').
                - "day_to_msgs" (defaultdict): Mapping from day to list of messages on that day.
                - "most_active_days" (list): Top 5 days with the most messages.
                - "most_common_words" (list): Top 20 most common valid words and their counts.

        Notes:
            - Uses jieba for Chinese word segmentation.
            - Filters out stopwords and punctuation.
        """
        stopwords = set([
            "我", "你", "的", "了", "在", "是", "和", "也", "有", "就", "不", "都", "吗", "啊", "吧", "哦", "呢", "着", "很", "还", "但", "与", "及", "或", "被", "为", "到", "说", "要", "会", "去", "他", "她", "它", "我们", "他们", "你们", "自己"
        ])
        punctuation = set("，。！？、；：“”‘’（）《》〈〉【】[]{}——-…,.!?;:\"'()<>[]{}")
        def is_valid_word(word):
            return word not in stopwords and word not in punctuation and re.match(r'\w', word)
        all_words = []
        word_counter = Counter()
        day_counter = Counter()
        month_counter = Counter()
        day_to_msgs = defaultdict(list)
        for m in messages_clean:
            date = m['CreateTime'].split(' ')[0]
            day_counter[date] += 1
            day_to_msgs[date].append(m)
            words = jieba.lcut(m['clean_msg'])
            valid_words = [w for w in words if is_valid_word(w)]
            all_words.extend(valid_words)
            word_counter.update(valid_words)
        for day in day_counter:
            month = day[:7]
            month_counter[month] += day_counter[day]
        most_active_days = [d for d, _ in day_counter.most_common(5)]
        most_common_words = word_counter.most_common(20)
        return {
            "all_words": all_words,
            "word_counter": word_counter,
            "day_counter": day_counter,
            "month_counter": month_counter,
            "day_to_msgs": day_to_msgs,
            "most_active_days": most_active_days,
            "most_common_words": most_common_words
        }


    @staticmethod
    def extract_json_from_text(text):
        if text is None:
            return None
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                return data
            except Exception as e:
                print("JSON解析失败:", e)
                return None
        else:
            print("未找到JSON数据")
            return None

    def push_to_neo4j(self, kg_json):
        node_map = {}
        for node in kg_json.get("nodes", []):
            node_id = node.get("id") or node.get("wxid")
            label = node.get("label", "User")
            n = Node(label, **{k: v for k, v in node.items() if k != "label"})
            self.graph.merge(n, label, "id")
            node_map[node_id] = n
        for rel in kg_json.get("relations", []):
            start_id = rel.get("start")
            end_id = rel.get("end")
            start_node = node_map.get(start_id)
            end_node = node_map.get(end_id)
            if start_node and end_node:
                r = Relationship(start_node, rel.get("type", "RELATES_TO"), end_node, **rel.get("properties", {}))
                self.graph.merge(r)


    def compress_sample_msgs(self, day_to_msgs, most_active_days, max_days=5, max_per_day=100):
        """
        对消息最多的几天的消息进行压缩，减少token消耗。
        1. 只保留每条消息的talker和msg字段。
        2. 每天最多保留max_per_day条消息，超出则从当天消息的最中间截取max_per_day条。
        3. 返回json字符串。
        """
        # 压缩消息
        compressed = []
        for d in most_active_days[:max_days]:
            msgs = day_to_msgs[d]
            n = len(msgs)
            if n > max_per_day:
                start = (n - max_per_day) // 2
                msgs = msgs[start:start + max_per_day]
            for m in msgs:
                compressed.append({
                    "talker": m.get("talker", ""),
                    "msg": m.get("msg", "")
                })

        return json.dumps({"messages": compressed}, ensure_ascii=False)


    def generate_knowledge_graph(
            self,
            messages,
            users,
            output_json_example=output_json_example,
            api_key=None
        ):
            """
            处理两人关系，生成知识图谱JSON。
            返回：(result_json) 元组
            """
            if api_key is None:
                api_key = self.llm_api_key_pool.get_api_key()
    
            wxid_list = list(users.keys())
            user1_wxid, user2_wxid = wxid_list[:2]
    
            # 消息预处理
            messages_clean = self.preprocess_messages(messages)
    
            # 信息抽取
            stats = self.extract_keywords_and_stats(messages_clean)
            sample_msgs_json = self.compress_sample_msgs(stats["day_to_msgs"], stats["most_active_days"])
    
            # 构建prompt
            prompt = build_prompt(
                json.dumps(users[user1_wxid], ensure_ascii=False),
                json.dumps(users[user2_wxid], ensure_ascii=False),
                json.dumps(dict(stats["month_counter"]), ensure_ascii=False),
                json.dumps(stats["most_common_words"], ensure_ascii=False),
                sample_msgs_json,
                output_json_example
            )
    
            # LLM调用
            response_text = call_llm(prompt, api_key=api_key)
    
            # 提取JSON
            result_json = self.extract_json_from_text(response_text)
            return result_json
    

    def push_address_nodes_and_relations(self, result_json):
        """
        检查所有User节点，若有country/province/city属性，则新建对应的Country/Province/City节点，并建立归属关系。
        同时将User节点与最详细的地点节点建立WECHAT_ADDRESS关系。
        """
        # 用于缓存已创建的地址节点，避免重复创建
        country_nodes = {}
        province_nodes = {}
        city_nodes = {}

        for node in result_json.get("nodes", []):
            if node.get("label") != "User":
                continue
            country = node.get("country", None)
            province = node.get("province", None)
            city = node.get("city", None)
            # 只处理有地址信息的节点
            if not country and not province and not city:
                continue

            # 创建Country节点
            country_node = None
            if country is not None:
                country_key = country
                if country_key in country_nodes:
                    country_node = country_nodes[country_key]
                else:
                    country_node = Node("Country", countryName=country)
                    self.graph.merge(country_node, "Country", "countryName")
                    country_nodes[country_key] = country_node

            # 创建Province节点
            province_node = None
            if province is not None:
                province_key = (country, province)
                if province_key in province_nodes:
                    province_node = province_nodes[province_key]
                else:
                    province_node = Node("Province", countryName=country, provinceName=province)
                    self.graph.merge(province_node, "Province", ("provinceName", "countryName"))
                    province_nodes[province_key] = province_node

            # 创建City节点
            city_node = None
            if city is not None:
                city_key = (country, province, city)
                if city_key in city_nodes:
                    city_node = city_nodes[city_key]
                else:
                    city_node = Node("City", countryName=country, provinceName=province, cityName=city)
                    self.graph.merge(city_node, "City", ("provinceName", "countryName", "cityName"))
                    city_nodes[city_key] = city_node

            # 建立归属关系
            # City 属于 Province
            if city_node and province_node:
                rel = Relationship(city_node, "LOCATED_IN_PROVINCE", province_node)
                self.graph.merge(rel)
            # City 属于 Country
            if city_node and country_node:
                rel = Relationship(city_node, "LOCATED_IN_COUNTRY", country_node)
                self.graph.merge(rel)
            # Province 属于 Country
            if province_node and country_node:
                rel = Relationship(province_node, "LOCATED_IN_COUNTRY", country_node)
                self.graph.merge(rel)

            # 新增：User节点与地点建立WECHAT_ADDRESS关系
            user_id = node.get("id") or node.get("wxid")
            user_label = node.get("label", "User")
            user_node = Node(user_label, **{k: v for k, v in node.items() if k != "label"})
            self.graph.merge(user_node, user_label, "id")

            # 优先city，其次province，再次country
            address_node = city_node or province_node or country_node
            if address_node:
                rel = Relationship(user_node, "WECHAT_ADDRESS", address_node)
                self.graph.merge(rel)

    def write_to_neo4j(self, result_json, user1_wxid, user2_wxid):
        """
        将知识图谱JSON写入Neo4j数据库。
        """
        try:
            if result_json:
                self.push_address_nodes_and_relations(result_json)  # 写入地址相关节点和关系
                self.push_to_neo4j(result_json)  # 写入知识图谱节点和关系
                node_count = len(result_json.get("nodes", []))
                edge_count = len(result_json.get("relations", []))
                logger.info(f"KG写入Neo4j成功：{user1_wxid} <-> {user2_wxid}，节点数：{node_count}，边数：{edge_count}")
                return True
            else:
                raise ValueError("KG生成失败")
        except Exception as e:
            logger.error(f"KG写入Neo4j异常：{user1_wxid} <-> {user2_wxid}，错误信息：{e}")
            return False
    
    def validate_kg_json(self, result_json):
        """
        验证知识图谱JSON是否符合要求，包括Neo4j类型检查
        
        Returns:
            tuple: (is_valid: bool, error_msg: str)
        """
        def is_valid_neo4j_value(value):
            """检查值是否为Neo4j支持的类型"""
            if value is None:
                return True
            
            # 基本类型检查
            if isinstance(value, (int, float, str, bool)):
                return True
                
            # 数组类型检查
            if isinstance(value, list):
                if not value:  # 空数组允许
                    return True
                # 检查是否所有元素类型相同且为基本类型
                first_type = type(value[0])
                if not all(isinstance(x, (int, float, str, bool)) for x in value):
                    return False
                if not all(isinstance(x, first_type) for x in value):
                    return False
                # 检查是否存在嵌套数组
                if any(isinstance(x, (list, dict)) for x in value):
                    return False
                return True
                
            # 日期时间类型检查
            if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
                return True
                
            return False

        try:
            if not result_json:
                return False, "llm返回结果为空"
                
            # 检查基本结构
            if not all(k in result_json for k in ["nodes", "relations"]):
                return False, "缺少nodes或relations字段"
                
            # 检查节点
            if not result_json["nodes"]:
                return False, "没有节点数据"
                
            # 检查节点属性
            for node in result_json["nodes"]:
                # 检查必要字段
                if not node.get("id"):
                    return False, "存在没有id的节点"
                if "label" not in node:
                    return False, "存在没有label的节点"
                    
                # 检查所有属性的类型
                for key, value in node.items():
                    if not is_valid_neo4j_value(value):
                        return False, f"节点属性类型错误: {key}={value} ({type(value).__name__})"
                        
            # 检查关系
            for rel in result_json.get("relations", []):
                # 检查必要字段
                if not all(k in rel for k in ["start", "end", "type"]):
                    return False, "关系缺少必要字段"
                    
                # 检查关系属性
                if "properties" in rel:
                    if not isinstance(rel["properties"], dict):
                        return False, "关系properties必须是字典类型"
                        
                    for key, value in rel["properties"].items():
                        if not is_valid_neo4j_value(value):
                            return False, f"关系属性类型错误: {key}={value} ({type(value).__name__})"
                            
            return True, "验证通过"
            
        except Exception as e:
            return False, f"验证过程发生错误: {str(e)}"

    def process_and_push_pair(self, 
                              messages, 
                              users, 
                              output_json_example=output_json_example, 
                              api_key=None):
        """
        完整处理流程的包装方法，包含重试逻辑
        """
        max_retries = 10
        retry_count = 0
        
        wxid_list = list(users.keys())
        user1_wxid, user2_wxid = wxid_list[:2]

        while retry_count < max_retries:
            result_json = self.generate_knowledge_graph(
                messages, users, output_json_example, api_key
            )
            
            # 验证生成的知识图谱
            is_valid, error_msg = self.validate_kg_json(result_json)
            

            if is_valid:
                return self.write_to_neo4j(result_json, user1_wxid, user2_wxid)
            else:
                retry_count += 1
                logger.warning(f"知识图谱Json验证失败 (第{retry_count}次尝试): {error_msg}")
                
                if retry_count >= max_retries:
                    logger.error(f"达到最大重试次数({max_retries})，处理失败: {user1_wxid} <-> {user2_wxid}")
                    return False
                
        return False