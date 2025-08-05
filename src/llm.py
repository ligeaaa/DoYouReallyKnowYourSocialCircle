import time
from google import genai
import pandas as pd
import random
from loguru import logger

def build_prompt(user1_info, user2_info, month_counter_json, most_common_words_json, sample_msgs_json, output_json_example) -> str:
    prompt = (
        "你是一个信息抽取系统，用于从我提供的微信聊天数据中提取实体、关系和属性，以便我之后建立 Neo4j 知识图谱。\n"
        "你必须只输出合法 JSON，不要包含任何额外解释性文字。\n"
        "\n"
        "【实体定义】\n"
        "- 实体(Entity)：包括人、事件、地点、话题等。\n"
        "- 关系(Relationship)：用于描述两人之间的互动类型，尽可能覆盖与两人联系紧密的关系，例如：\n"
        "  - 社交关系：同学、朋友、同事、亲属等\n"
        "  - 情感关系：喜欢、爱慕、相恋、暧昧等\n"
        "  - 指导关系：教导、指导、帮助等\n"
        "  - 其他重要互动：经常聊天、频繁互动、长期无联系等\n"
        "- 关系方向：如果关系是双向的，添加双向关系；如果是单向的，添加单向关系。\n"
        "- 关系的设置原则：每条关系应只描述一种关系类型，避免多重关系混合。如果有多种关系，应该建立多条关系\n"
        "- 属性(Properties)：仅包含必要的附加信息（如时间范围、互动强度等），避免无关内容。且属性值只允许为字符串、数字、布尔值、列表，不允许为其它\n"
        "- 原则：将主要的两位用户（即聊天的双方）设置为User，聊天过程中如果高频率出现其它实体，则根据情况设置为User之外的标签，如果不确定，则设置为other。\n"
        "\n"
        "【输入数据】\n"
        f"用户1的信息为：{user1_info}\n"
        f"用户2的信息为：{user2_info}\n"
        f"二者每个月的聊天数量（JSON）：{month_counter_json}\n"
        f"二者聊天的高频词（JSON，去掉常见词后 Top 20）：{most_common_words_json}\n"
        f"二者聊天最多的几天完整文本（JSON）：{sample_msgs_json}\n"
        "\n"
        "【输出要求】\n"
        "请根据以上信息，严格按以下 JSON 格式输出结果，必须包含所给例子中的所有属性，根据实际情况添加更多的属性：\n"
        f"{output_json_example}\n"
        "仅返回JSON，不要包含解释性文字。"
    )
    return prompt


def call_llm(prompt, api_key, model="gemini-2.5-flash", max_retries=3, retry_delay=5):
    """
    调用LLM API并自动重试
    
    Args:
        prompt: 提示词
        api_key: API密钥
        model: 模型名称
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    """
    client = genai.Client(api_key=api_key)
    
    for attempt in range(max_retries):
        start_time = time.time()
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            end_time = time.time()
            logger.info(f"LLM调用完成，用时 {end_time - start_time:.2f} 秒")
            return response.text
            
        except Exception as e:
            end_time = time.time()
            logger.error(f"LLM调用失败（第{attempt + 1}次尝试），用时 {end_time - start_time:.2f} 秒")
            logger.error(f"错误详情：{e}")
            
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"达到最大重试次数 ({max_retries})，调用失败")
                return None

class GeminiApiPOOL():
    def __init__(self, api_keys_file):
        self.api_keys_file = api_keys_file
        self.api_keys = self.load_api_keys()

    def load_api_keys(self):
        df = pd.read_excel(self.api_keys_file)
        return df['api_key'].tolist()
    
    def get_api_key(self):
        return random.choice(self.api_keys)
