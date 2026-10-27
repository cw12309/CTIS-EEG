# -*- coding: utf-8 -*-
"""
CTIS-EEG 五大认知训练任务题库 (MMSE/MoCA 临床对齐版)

设计依据:
  - MMSE (简易精神状态检查): 定向力10分、记忆力3分、注意计算5分、回忆3分、语言8分、视空间1分
  - MoCA (蒙特利尔认知评估): 视空间执行5分、命名3分、注意6分、语言3分、抽象2分、延迟回忆5分、定向6分
  - 中文版MoCA北京版: 面孔/天鹅绒/教堂/菊花/红色 五词延迟回忆

评分体系 (CT-30):
  - 每项满分 6 分，5 项合计 30 分
  - D1 orient:     定向问答正确率 x 6 (对齐MMSE定向10题)
  - D2 memencode:  即刻回忆(2分) + 延迟回忆(3分) + 再认(1分) (对齐MoCA五词延迟回忆)
  - D3 trailblink: 连线时间(2分) + 连线错误(2分) + 数字倒背(2分) (对齐MoCA连线+注意)
  - D4 semflow:    命名正确(2分) + 语义流畅性(2分) + 相似性抽象(2分) (对齐MoCA命名+抽象)
  - D5 nameblink:  首次正确率(3分) + 渐进提示(2分) + 复述(1分) (对齐MoCA命名+语言复述)
"""

import random

TASK_BANK = {

    # ============================================================
    # 任务1: EEG-Orient 定向力训练
    # 对齐: MMSE定向力10题(时间5+地点5) + MoCA定向6题(日期+地点)
    # 每套10题: 时间定向5题(动态生成) + 常识定向5题(固定答案)
    # 注: 原地点定向(省市区/楼层)因无确定答案，改为常识定向
    # ============================================================
    "orient": {
        "name": "EEG-Orient 定向力训练",
        "description": "时间与个人/常识定向评估，对齐MMSE定向力10题标准",
        "scenes": [
            {
                "set_name": "标准定向评估A",
                "trials": [
                    # 时间定向 (5题, 对齐MMSE, 答案由后端动态生成)
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 个人/常识定向 (5题, 对齐MMSE地点定向)
                    # 改为有确定答案的常识题，而非因人而异的地点题
                    {"prompt": "中国的首都是哪个城市？", "image": "", "options": ["北京", "上海", "广州", "南京"], "answer": 0, "domain": "knowledge"},
                    {"prompt": "一年有多少个月？", "image": "", "options": ["10个", "11个", "12个", "13个"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "一周有多少天？", "image": "", "options": ["5天", "6天", "7天", "8天"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "一天有多少小时？", "image": "", "options": ["12小时", "20小时", "24小时", "36小时"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "一小时有多少分钟？", "image": "", "options": ["30分钟", "60分钟", "90分钟", "100分钟"], "answer": 1, "domain": "knowledge"},
                ],
            },
            {
                "set_name": "标准定向评估B",
                "trials": [
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 常识定向
                    {"prompt": "中国的国旗是什么颜色？", "image": "", "options": ["红色", "蓝色", "黄色", "绿色"], "answer": 0, "domain": "knowledge"},
                    {"prompt": "太阳从哪个方向升起？", "image": "", "options": ["东方", "西方", "南方", "北方"], "answer": 0, "domain": "knowledge"},
                    {"prompt": "一个月最多有多少天？", "image": "", "options": ["28天", "30天", "31天", "32天"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "一年有多少个季节？", "image": "", "options": ["2个", "3个", "4个", "6个"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "一分钟有多少秒？", "image": "", "options": ["30秒", "60秒", "90秒", "100秒"], "answer": 1, "domain": "knowledge"},
                ],
            },
            {
                "set_name": "标准定向评估C",
                "trials": [
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 常识定向
                    {"prompt": "水在多少度会沸腾？", "image": "", "options": ["50度", "80度", "100度", "120度"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "地球绕太阳一圈需要多长时间？", "image": "", "options": ["一个月", "半年", "一年", "两年"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "中秋节通常在农历几月？", "image": "", "options": ["正月", "五月", "八月", "十二月"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "春节是在哪个季节？", "image": "", "options": ["春季", "夏季", "秋季", "冬季"], "answer": 0, "domain": "knowledge"},
                    {"prompt": "中国最大的城市是哪个？", "image": "", "options": ["北京", "上海", "广州", "深圳"], "answer": 1, "domain": "knowledge"},
                ],
            },
            {
                "set_name": "标准定向评估D",
                "trials": [
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 常识定向
                    {"prompt": "长江是中国的第几大河？", "image": "", "options": ["第二大", "第一大", "第三大", "第四大"], "answer": 1, "domain": "knowledge"},
                    {"prompt": "月亮绕地球一圈大约需要多少天？", "image": "", "options": ["7天", "15天", "30天", "60天"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "端午节是为了纪念哪位历史人物？", "image": "", "options": ["孔子", "屈原", "李白", "诸葛亮"], "answer": 1, "domain": "knowledge"},
                    {"prompt": "一年有多少个星期？", "image": "", "options": ["48个", "50个", "52个", "54个"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "中国的国球是什么？", "image": "", "options": ["篮球", "足球", "乒乓球", "羽毛球"], "answer": 2, "domain": "knowledge"},
                ],
            },
            {
                "set_name": "标准定向评估E",
                "trials": [
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 常识定向
                    {"prompt": "中国的长城有多长？", "image": "", "options": ["一千多公里", "五千多公里", "两万多公里", "十万公里"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "太阳从哪个方向落下？", "image": "", "options": ["东方", "西方", "南方", "北方"], "answer": 1, "domain": "knowledge"},
                    {"prompt": "人体正常体温大约是多少度？", "image": "", "options": ["35度", "36.5度", "37.5度", "39度"], "answer": 1, "domain": "knowledge"},
                    {"prompt": "国庆节是几月几号？", "image": "", "options": ["一月一日", "五月一日", "八月一日", "十月一日"], "answer": 3, "domain": "knowledge"},
                    {"prompt": "中国有多少个省级行政区？", "image": "", "options": ["23个", "30个", "34个", "40个"], "answer": 2, "domain": "knowledge"},
                ],
            },
            {
                "set_name": "标准定向评估F",
                "trials": [
                    {"prompt": "现在是哪一年？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是几月份？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是几号？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "今天是星期几？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    {"prompt": "现在是什么季节？", "image": "", "options": [], "answer": 0, "domain": "time"},
                    # 常识定向
                    {"prompt": "黄河流入哪个海？", "image": "", "options": ["东海", "南海", "渤海", "黄海"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "元宵节是农历几月几日？", "image": "", "options": ["正月初一", "正月十五", "二月初二", "五月初五"], "answer": 1, "domain": "knowledge"},
                    {"prompt": "世界上最长的河流是哪条？", "image": "", "options": ["长江", "亚马逊河", "尼罗河", "密西西比河"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "中国的货币叫什么？", "image": "", "options": ["美元", "日元", "人民币", "港币"], "answer": 2, "domain": "knowledge"},
                    {"prompt": "人有多少颗牙齿（成人）？", "image": "", "options": ["20颗", "28颗", "32颗", "36颗"], "answer": 2, "domain": "knowledge"},
                ],
            },
        ],
    },

    # ============================================================
    # 任务2: EEG-MemEncode 情景记忆训练
    # 对齐: MoCA五词延迟回忆 (面孔/天鹅绒/教堂/菊花/红色)
    # 范式: 编码(5词×2次) → 干扰(定向题) → 延迟回忆(自由回忆) → 再认(目标+干扰)
    # ============================================================
    "memencode": {
        "name": "EEG-MemEncode 情景记忆训练",
        "description": "五词编码-延迟-回忆范式，对齐MoCA延迟回忆评估",
        "scenes": [
            {
                "set_name": "MoCA标准词表",
                "encoding_words": ["面孔", "天鹅绒", "教堂", "菊花", "红色"],
                "distractors_semantic": ["容貌", "丝绸", "寺庙", "玫瑰", "蓝色"],
                "distractors_unrelated": ["火车", "锤子", "冰箱", "钢琴", "沙漠"],
                "delay_questions": [
                    {"prompt": "100连续减7，93减7等于多少？", "options": ["84", "86", "88", "90"], "answer": 1},
                    {"prompt": "现在是什么季节？", "options": ["春季", "夏季", "秋季", "冬季"], "answer": 0},
                ],
            },
            {
                "set_name": "日常生活词表",
                "encoding_words": ["早餐", "钥匙", "花园", "电话", "报纸"],
                "distractors_semantic": ["午餐", "门锁", "公园", "手机", "杂志"],
                "distractors_unrelated": ["火箭", "钻石", "企鹅", "吉他", "冰川"],
                "delay_questions": [
                    {"prompt": "从50开始，每次减3，下一个数是？", "options": ["44", "45", "47", "48"], "answer": 2},
                    {"prompt": "您现在在几楼？", "options": ["一楼", "三楼", "五楼", "七楼"], "answer": 1},
                ],
            },
            {
                "set_name": "自然事物词表",
                "encoding_words": ["大树", "河流", "白云", "蝴蝶", "阳光"],
                "distractors_semantic": ["小树", "小溪", "乌云", "蜻蜓", "月光"],
                "distractors_unrelated": ["电脑", "螺丝", "冰箱", "篮球", "字典"],
                "delay_questions": [
                    {"prompt": "请倒着说'6-2-9'，应该是？", "options": ["9-2-6", "6-9-2", "2-6-9", "9-6-2"], "answer": 0},
                    {"prompt": "您现在所在的城市是？", "options": ["北京", "上海", "广州", "成都"], "answer": 0},
                ],
            },
        ],
    },

    # ============================================================
    # 任务3: EEG-TrailBlink 执行功能训练
    # 对齐: MoCA连线测试(TMT-B: 数字-字母交替) + 注意力(数字倒背/连续减7)
    # 子模块A: 连线测试 (1-A-2-B-3-C...)
    # 子模块B: 数字倒背 (对齐MoCA注意力)
    # 子模块C: 连续减7 (对齐MMSE注意计算)
    # ============================================================
    "trailblink": {
        "name": "EEG-TrailBlink 执行功能训练",
        "description": "连线测试+数字倒背+连续减7，对齐MoCA执行功能与注意力评估",
        "max_time_sec": {"L1": 180, "L2": 150, "L3": 120},
        "scenes": [
            {
                "set_name": "基础执行功能",
                "sequence": ["1", "A", "2", "B", "3", "C"],
                "grid_size": 3,
                "digit_span": [
                    {"digits": "2-1-9", "answer": "9-1-2"},
                    {"digits": "5-8-2", "answer": "2-8-5"},
                ],
                "serial_seven": [
                    {"start": 100, "steps": [93, 86, 79]},
                ],
            },
            {
                "set_name": "标准执行功能",
                "sequence": ["1", "A", "2", "B", "3", "C", "4", "D"],
                "grid_size": 4,
                "digit_span": [
                    {"digits": "6-2-9-4", "answer": "4-9-2-6"},
                    {"digits": "3-7-1-8", "answer": "8-1-7-3"},
                ],
                "serial_seven": [
                    {"start": 100, "steps": [93, 86, 79, 72]},
                ],
            },
            {
                "set_name": "挑战执行功能",
                "sequence": ["1", "A", "2", "B", "3", "C", "4", "D", "5", "E"],
                "grid_size": 5,
                "digit_span": [
                    {"digits": "7-3-9-1-4", "answer": "4-1-9-3-7"},
                    {"digits": "5-8-2-6-3", "answer": "3-6-2-8-5"},
                ],
                "serial_seven": [
                    {"start": 100, "steps": [93, 86, 79, 72, 65]},
                ],
            },
        ],
    },

    # ============================================================
    # 任务4: EEG-SemFlow 语义记忆训练
    # 对齐: MoCA命名(狮子/犀牛/骆驼) + 语言流畅性 + 相似性抽象
    # 子模块A: 命名 (对齐MoCA命名3题)
    # 子模块B: 语义流畅性 (对齐MoCA语言流畅性，1分钟说出≥11个动物)
    # 子模块C: 相似性 (对齐MoCA抽象思维：橙子-香蕉=水果，火车-自行车=交通工具)
    # ============================================================
    "semflow": {
        "name": "EEG-SemFlow 语义记忆训练",
        "description": "命名+语义流畅性+相似性抽象，对齐MoCA命名/语言/抽象评估",
        "scenes": [
            {
                "set_name": "MoCA标准语义",
                "module_a": {
                    "description": "命名动物 (对齐MoCA命名3题)",
                    "trials": [
                        {"emoji": "\U0001F981", "prompt": "请说出这是什么动物？", "options": ["狮子", "老虎", "豹子", "狼"], "answer": 0},
                        {"emoji": "\U0001F98F", "prompt": "请说出这是什么动物？", "options": ["河马", "犀牛", "大象", "野猪"], "answer": 1},
                        {"emoji": "\U0001F42B", "prompt": "请说出这是什么动物？", "options": ["马", "骆驼", "鹿", "驴"], "answer": 1},
                    ],
                },
                "module_b": {
                    "description": "语义流畅性 (对齐MoCA: 1分钟说出尽可能多的动物)",
                    "time_limit_sec": 60,
                    "category": "动物",
                    "threshold": 11,
                },
                "module_c": {
                    "description": "相似性判断 (对齐MoCA抽象思维)",
                    "trials": [
                        {"prompt": "橙子和香蕉有什么相同之处？", "options": ["都是水果", "都是蔬菜", "都是饮料", "都是主食"], "answer": 0},
                        {"prompt": "火车和自行车有什么相同之处？", "options": ["都是家具", "都是交通工具", "都是玩具", "都是电器"], "answer": 1},
                        {"prompt": "手表和尺子有什么相同之处？", "options": ["都是食物", "都是测量工具", "都是文具", "都是装饰品"], "answer": 1},
                    ],
                },
            },
            {
                "set_name": "日常语义",
                "module_a": {
                    "description": "命名日常物品",
                    "trials": [
                        {"emoji": "\u231A", "prompt": "请说出这是什么？", "options": ["手表", "时钟", "手机", "计算器"], "answer": 0},
                        {"emoji": "\U0001F4BB", "prompt": "请说出这是什么？", "options": ["电视", "电脑", "收音机", "打印机"], "answer": 1},
                        {"emoji": "\U0001F4DA", "prompt": "请说出这是什么？", "options": ["报纸", "字典", "书本", "信件"], "answer": 2},
                    ],
                },
                "module_b": {
                    "description": "语义流畅性 (1分钟说出尽可能多的蔬菜)",
                    "time_limit_sec": 60,
                    "category": "蔬菜",
                    "threshold": 11,
                },
                "module_c": {
                    "description": "相似性判断",
                    "trials": [
                        {"prompt": "椅子和桌子有什么相同之处？", "options": ["都是家具", "都是电器", "都是食物", "都是文具"], "answer": 0},
                        {"prompt": "牛奶和果汁有什么相同之处？", "options": ["都是主食", "都是饮品", "都是调味品", "都是药品"], "answer": 1},
                        {"prompt": "铅笔和毛笔有什么相同之处？", "options": ["都是工具", "都是书写工具", "都是玩具", "都是餐具"], "answer": 1},
                    ],
                },
            },
            {
                "set_name": "扩展语义",
                "module_a": {
                    "description": "命名交通工具",
                    "trials": [
                        {"emoji": "\u2708", "prompt": "请说出这是什么？", "options": ["飞机", "火箭", "气球", "风筝"], "answer": 0},
                        {"emoji": "\U0001F6A2", "prompt": "请说出这是什么？", "options": ["小船", "轮船", "潜艇", "竹筏"], "answer": 1},
                        {"emoji": "\U0001F697", "prompt": "请说出这是什么？", "options": ["汽车", "火车", "公交车", "卡车"], "answer": 0},
                    ],
                },
                "module_b": {
                    "description": "语义流畅性 (1分钟说出尽可能多的城市)",
                    "time_limit_sec": 60,
                    "category": "城市",
                    "threshold": 11,
                },
                "module_c": {
                    "description": "相似性判断",
                    "trials": [
                        {"prompt": "春天和秋天有什么相同之处？", "options": ["都是季节", "都是天气", "都是月份", "都是节日"], "answer": 0},
                        {"prompt": "钢琴和小提琴有什么相同之处？", "options": ["都是乐器", "都是家具", "都是工具", "都是玩具"], "answer": 0},
                        {"prompt": "医院和学校有什么相同之处？", "options": ["都是商店", "都是公共场所", "都是餐厅", "都是公园"], "answer": 1},
                    ],
                },
            },
        ],
    },

    # ============================================================
    # 任务5: EEG-NameBlink 命名能力训练
    # 对齐: MoCA命名(3分) + 语言复述(2分) + 渐进提示范式
    # 子模块A: 命名 (物体命名+梯度提示: 自由命名→类别提示→首字提示)
    # 子模块B: 复述 (对齐MoCA语言复述: "我只知道今天张明是和李亮一起来的")
    # ============================================================
    "nameblink": {
        "name": "EEG-NameBlink 命名能力训练",
        "description": "物体命名+复述+渐进提示，对齐MoCA命名与语言复述评估",
        "scenes": [
            {
                "set_name": "MoCA标准命名",
                "trials": [
                    {
                        "image_desc": "一种大型猫科动物，雄性有鬃毛，被称为'百兽之王'",
                        "emoji": "\U0001F981",
                        "prompt": "请说出这是什么动物？",
                        "options": ["狮子", "老虎", "豹子", "熊"],
                        "answer": 0,
                        "hint_category": "大型猫科动物",
                        "hint_initial": "狮",
                    },
                    {
                        "image_desc": "一种大型厚皮动物，鼻子上有一个或两个角",
                        "emoji": "\U0001F98F",
                        "prompt": "请说出这是什么动物？",
                        "options": ["河马", "犀牛", "大象", "野猪"],
                        "answer": 1,
                        "hint_category": "厚皮动物",
                        "hint_initial": "犀",
                    },
                    {
                        "image_desc": "一种沙漠动物，背上有驼峰，被称为'沙漠之舟'",
                        "emoji": "\U0001F42B",
                        "prompt": "请说出这是什么动物？",
                        "options": ["马", "骆驼", "鹿", "驴"],
                        "answer": 1,
                        "hint_category": "沙漠动物",
                        "hint_initial": "骆",
                    },
                ],
                "repetition": [
                    {"sentence": "我只知道今天张明是和李亮一起来的", "options": ["我只知道今天张明是和李亮一起来的", "我知道今天张明和李亮来了", "张明和李亮今天来了", "今天张明来了"], "answer": 0},
                    {"sentence": "当狗在房间里时，猫总是躲在沙发下面", "options": ["当狗在房间里时，猫总是躲在沙发下面", "狗在房间里，猫躲在沙发下", "猫总是躲在沙发下面", "狗和猫在房间里"], "answer": 0},
                ],
            },
            {
                "set_name": "日常用品命名",
                "trials": [
                    {
                        "image_desc": "一种戴在手腕上用来看时间的物品",
                        "emoji": "\u231A",
                        "prompt": "请说出这是什么？",
                        "options": ["手表", "手镯", "手链", "计时器"],
                        "answer": 0,
                        "hint_category": "计时工具",
                        "hint_initial": "手",
                    },
                    {
                        "image_desc": "一种用来照明的电器，按开关会亮",
                        "emoji": "\U0001F4A1",
                        "prompt": "请说出这是什么？",
                        "options": ["灯泡", "蜡烛", "火把", "手电筒"],
                        "answer": 0,
                        "hint_category": "照明工具",
                        "hint_initial": "灯",
                    },
                    {
                        "image_desc": "一种用来写字的工具，需要削尖使用",
                        "emoji": "\u270F",
                        "prompt": "请说出这是什么？",
                        "options": ["铅笔", "钢笔", "毛笔", "蜡笔"],
                        "answer": 0,
                        "hint_category": "书写工具",
                        "hint_initial": "铅",
                    },
                ],
                "repetition": [
                    {"sentence": "七十四岁的老人每天早上在公园里打太极拳", "options": ["七十四岁的老人每天早上在公园里打太极拳", "老人每天早上打太极拳", "七十四岁老人在公园打拳", "老人在公园锻炼"], "answer": 0},
                    {"sentence": "老师让学生把作业本和课本都放在桌子上", "options": ["老师让学生把作业本和课本都放在桌子上", "学生把作业放在桌上", "老师让学生放课本", "作业本和课本在桌上"], "answer": 0},
                ],
            },
            {
                "set_name": "常见食物命名",
                "trials": [
                    {
                        "image_desc": "一种红色的水果，圆形，脆甜，一天一个远离医生",
                        "emoji": "\U0001F34E",
                        "prompt": "请说出这是什么？",
                        "options": ["苹果", "番茄", "樱桃", "草莓"],
                        "answer": 0,
                        "hint_category": "水果",
                        "hint_initial": "苹",
                    },
                    {
                        "image_desc": "一种白色的液体饮品，来自奶牛",
                        "emoji": "\U0001F95B",
                        "prompt": "请说出这是什么？",
                        "options": ["牛奶", "豆浆", "椰汁", "米汤"],
                        "answer": 0,
                        "hint_category": "饮品",
                        "hint_initial": "牛",
                    },
                    {
                        "image_desc": "一种黄色的主食，用玉米做成，常做早餐",
                        "emoji": "\U0001F35A",
                        "prompt": "请说出这是什么？",
                        "options": ["米饭", "玉米粥", "面条", "馒头"],
                        "answer": 1,
                        "hint_category": "主食",
                        "hint_initial": "玉",
                    },
                ],
                "repetition": [
                    {"sentence": "小明和小红约好了周末一起去图书馆看书", "options": ["小明和小红约好了周末一起去图书馆看书", "小明和小红周末去图书馆", "他们约好周末看书", "小明去图书馆看书"], "answer": 0},
                    {"sentence": "外面下着大雨但是妈妈还是准时来接我放学", "options": ["外面下着大雨但是妈妈还是准时来接我放学", "妈妈下雨天来接我", "妈妈准时接我放学", "下大雨妈妈来接我"], "answer": 0},
                ],
            },
        ],
    },
}


def pick_random_scene(task_key):
    """随机抽取一套题目"""
    task = TASK_BANK.get(task_key)
    if not task:
        return None
    scene = random.choice(task["scenes"])
    return scene


def compute_ct30(results):
    """
    计算 CT-30 认知训练总分 (对齐MMSE/MoCA)
    results: dict, key 为任务名, value 为该任务的详细结果

    返回: {
        "orient": 0-6,
        "memencode": 0-6,
        "trailblink": 0-6,
        "semflow": 0-6,
        "nameblink": 0-6,
        "ct30": 0-30,
        "vector": {"D1":0-1, "D2":0-1, "D3":0-1, "D4":0-1, "D5":0-1}
    }
    """
    scores = {}

    # 1. orient: 定向问答正确率 x 6 (对齐MMSE 10题定向力)
    orient = results.get("orient", {})
    orient_total = orient.get("total", 0)
    orient_correct = orient.get("correct", 0)
    if orient_total > 0:
        scores["orient"] = round(orient_correct / orient_total * 6, 2)
    else:
        scores["orient"] = 0

    # 2. memencode: 即刻回忆(2分) + 延迟回忆(3分) + 再认(1分) (对齐MoCA五词延迟回忆)
    mem = results.get("memencode", {})
    # 即刻回忆: 第2次编码正确数/5 x 2
    immediate_correct = mem.get("immediate_correct", 0)
    immediate_total = mem.get("immediate_total", 5)
    immediate_rate = immediate_correct / immediate_total if immediate_total > 0 else 0
    # 延迟回忆: 正确回忆数/5 x 3
    target_total = mem.get("target_total", 5)
    target_correct = mem.get("target_correct", 0)
    recall_rate = target_correct / target_total if target_total > 0 else 0
    # 再认: (1-虚报率) x 1
    distractor_total = mem.get("distractor_total", 0)
    distractor_false_alarm = mem.get("distractor_false_alarm", 0)
    false_alarm_rate = distractor_false_alarm / distractor_total if distractor_total > 0 else 0
    scores["memencode"] = round(immediate_rate * 2 + recall_rate * 3 + (1 - false_alarm_rate) * 1, 2)

    # 3. trailblink: 连线时间(2分) + 连线错误(2分) + 数字倒背(2分) (对齐MoCA连线+注意)
    trail = results.get("trailblink", {})
    actual_time = trail.get("time_sec", 0)
    max_time = trail.get("max_time_sec", 120)
    errors = trail.get("errors", 0)
    seq_len = trail.get("sequence_length", 8)
    time_rate = max(0, 1 - actual_time / max_time) if max_time > 0 else 0
    max_errors = seq_len * 0.5
    error_rate = max(0, 1 - errors / max_errors) if max_errors > 0 else 0
    # 数字倒背正确率
    span_correct = trail.get("span_correct", 0)
    span_total = trail.get("span_total", 2)
    span_rate = span_correct / span_total if span_total > 0 else 0
    scores["trailblink"] = round(time_rate * 2 + error_rate * 2 + span_rate * 2, 2)

    # 4. semflow: 命名正确(2分) + 语义流畅性(2分) + 相似性抽象(2分) (对齐MoCA命名+抽象)
    sem = results.get("semflow", {})
    naming_correct = sem.get("naming_correct", 0)
    naming_total = sem.get("naming_total", 3)
    naming_rate = naming_correct / naming_total if naming_total > 0 else 0
    # 流畅性: 达到阈值11个满分，0个0分，线性插值
    fluency_count = sem.get("fluency_count", 0)
    fluency_threshold = sem.get("fluency_threshold", 11)
    fluency_rate = min(1, fluency_count / fluency_threshold) if fluency_threshold > 0 else 0
    # 相似性
    sim_correct = sem.get("similarity_correct", 0)
    sim_total = sem.get("similarity_total", 3)
    sim_rate = sim_correct / sim_total if sim_total > 0 else 0
    scores["semflow"] = round(naming_rate * 2 + fluency_rate * 2 + sim_rate * 2, 2)

    # 5. nameblink: 首次正确率(3分) + 渐进提示(2分) + 复述(1分) (对齐MoCA命名+复述)
    name = results.get("nameblink", {})
    first_correct = name.get("first_correct", 0)
    name_total = name.get("total", 3)
    hint_needed = name.get("hint_needed", 0)
    passive_learn = name.get("passive_learn", 0)
    # 复述正确率
    repeat_correct = name.get("repeat_correct", 0)
    repeat_total = name.get("repeat_total", 2)
    first_rate = first_correct / name_total if name_total > 0 else 0
    hint_rate = hint_needed / name_total if name_total > 0 else 0
    passive_rate = passive_learn / name_total if name_total > 0 else 0
    repeat_rate = repeat_correct / repeat_total if repeat_total > 0 else 0
    scores["nameblink"] = round(first_rate * 3 + (1 - hint_rate) * 1 + (1 - passive_rate) * 1 + repeat_rate * 1, 2)

    # 总分
    ct30 = round(sum(scores.values()), 2)

    # 五维认知向量 (归一化到 0-1)
    vector = {
        "D1": round(scores["orient"] / 6, 4),
        "D2": round(scores["memencode"] / 6, 4),
        "D3": round(scores["trailblink"] / 6, 4),
        "D4": round(scores["semflow"] / 6, 4),
        "D5": round(scores["nameblink"] / 6, 4),
    }

    return {"scores": scores, "ct30": ct30, "vector": vector}
