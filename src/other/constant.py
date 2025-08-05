folder_path = r"/Users/lige/data/DYKYRSC/wechat/json"

master_user_id = "wxid_yner05jjwmry11"

NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "Qq1324657980"

output_json_example = """
{//属性值只允许为字符串、数字、布尔值、列表，不允许为其它
  "nodes": [ // 节点列表，每个节点代表一个实体（如用户）
    {
      "id": "wxid_xxx", // 节点唯一标识（wxID）
      "label": "User",             // 节点类型（用户或者其它）。将主要的两位用户（即聊天的双方）设置为User，聊天过程中如果高频率出现其它实体，则根据情况设置为User之外的标签，如果不确定，则统一设置为other。如果实体不是人，则根据实际情况设置node中的属性
      "nickname": "xxx",          // 用户昵称
      "remark": "",                // 用户备注（不一定有）
      "account": "123456789", // 用户账号
      "gender": 1,                 // 性别（1男，2女，0未知）
      "signature": "为",    // 个性签名
      "country": "country",             // 国家（不一定有）
      "province": "province",      // 省份（不一定有）
      "city": "city",           // 城市（不一定有）
      "mobile": "",                // 手机号（不一定有）
      "LabelIDList": []            // 标签ID列表（不一定有，若有，应重点参考）
    }
  ],
  "relations": [ // 关系列表，每个关系描述两个节点之间的联系
    {
      "start": "wxid_xxx", // 起始节点ID（微信ID）
      "end": "wxid_yyy",   // 结束节点ID（微信ID）
      "type": "Friend",            // 关系类型（如聊天、朋友等，单向关系用简单明了的动词或者动词词组，双向关系用简单明了的名词或名词词组）
      "properties": {                 // 关系属性
        "month": ["yyyy-mm", "yyyy-mm", "yyyy-mm"],  // 聊天发生的月份
        "total_msg_count": 123,       // 总聊天消息数量
        "relationship_summary": "聊天频率极高，彼此关系密切", // 简短的关系总结
      }
    }
  ]
}
"""