"""
评估问卷配置
统一维护字段元数据、分组定义和结构化交互配置。
"""

from __future__ import annotations

from typing import Any, Dict, List


YES_NO_OPTIONS = [
    {"label": "是", "value": "是"},
    {"label": "否", "value": "否"},
]

HEALTH_LIMITATION_OPTIONS = [
    {"label": "完全没有影响", "value": "完全没有影响"},
    {"label": "有一点影响", "value": "有一点影响"},
    {"label": "影响比较明显", "value": "影响比较明显"},
    {"label": "影响很大，很多事情都需要别人帮忙", "value": "影响很大"},
]

BADL_OPTIONS = [
    {"label": "不需要帮助", "value": "不需要帮助"},
    {"label": "需要别人搭把手", "value": "需要别人搭把手"},
    {"label": "大部分要靠别人帮忙", "value": "大部分要靠别人帮忙"},
]

IADL_OPTIONS = [
    {"label": "能自己做", "value": "能自己做"},
    {"label": "做起来有点困难", "value": "做起来有点困难"},
    {"label": "现在做不了", "value": "现在做不了"},
]

FREQUENCY_OPTIONS = [
    {"label": "从不", "value": "从不"},
    {"label": "很少", "value": "很少"},
    {"label": "有时", "value": "有时"},
    {"label": "经常", "value": "经常"},
]

SMOKING_DRINKING_OPTIONS = [
    {"label": "从不", "value": "从不"},
    {"label": "已戒", "value": "已戒"},
    {"label": "偶尔", "value": "偶尔"},
    {"label": "每天", "value": "每天"},
]

SLEEP_OPTIONS = [
    {"label": "很好", "value": "很好"},
    {"label": "好", "value": "好"},
    {"label": "一般", "value": "一般"},
    {"label": "差", "value": "差"},
    {"label": "很差", "value": "很差"},
]

VISION_HEARING_OPTIONS = [
    {"label": "好", "value": "好"},
    {"label": "一般", "value": "一般"},
    {"label": "差", "value": "差"},
]

RESIDENCE_OPTIONS = [
    {"label": "城市", "value": "城市"},
    {"label": "农村", "value": "农村"},
]

SEX_OPTIONS = [
    {"label": "男士", "value": "男"},
    {"label": "女士", "value": "女"},
]

MARITAL_OPTIONS = [
    {"label": "在婚", "value": "在婚"},
    {"label": "丧偶", "value": "丧偶"},
    {"label": "离婚", "value": "离婚"},
    {"label": "未婚", "value": "未婚"},
    {"label": "其他", "value": "其他"},
]

CHRONIC_ANY_OPTIONS = [
    {"label": "有", "value": "有"},
    {"label": "没有", "value": "没有"},
    {"label": "记不清", "value": "记不清"},
]

LIVING_ARRANGEMENT_OPTIONS = [
    {"label": "独居", "value": "独居"},
    {"label": "和老伴", "value": "和老伴"},
    {"label": "和子女", "value": "和子女"},
    {"label": "和老伴及子女", "value": "和老伴及子女"},
    {"label": "住养老院", "value": "住养老院"},
]

CAREGIVER_OPTIONS = [
    {"label": "子女", "value": "子女"},
    {"label": "老伴", "value": "老伴"},
    {"label": "保姆", "value": "保姆"},
    {"label": "自己", "value": "自己"},
    {"label": "无人", "value": "无人"},
    {"label": "其他", "value": "其他"},
]

FINANCIAL_OPTIONS = [
    {"label": "很好", "value": "很好"},
    {"label": "好", "value": "好"},
    {"label": "一般", "value": "一般"},
    {"label": "差", "value": "差"},
    {"label": "很差", "value": "很差"},
]

MEDICAL_INSURANCE_OPTIONS = [
    {"label": "城镇职工医保", "value": "城镇职工医保"},
    {"label": "城乡居民医保", "value": "城乡居民医保"},
    {"label": "新农合", "value": "新农合"},
    {"label": "商业保险", "value": "商业保险"},
    {"label": "无", "value": "无"},
    {"label": "不清楚", "value": "不清楚"},
    {"label": "其他", "value": "其他"},
]

FIELD_META: Dict[str, Dict[str, Any]] = {
    "age": {"zh": "年龄", "hint": "数字，如 82"},
    "sex": {"zh": "性别", "hint": "男 / 女"},
    "residence": {"zh": "居住地类型", "hint": "城市 / 农村"},
    "education_years": {"zh": "受教育年限", "hint": "数字，如 6"},
    "marital_status": {"zh": "婚姻状况", "hint": "在婚 / 丧偶 / 离婚 / 未婚 / 其他"},
    "weight": {"zh": "体重（公斤）", "hint": "数字，如 55"},
    "height": {"zh": "身高（厘米）", "hint": "数字，如 160"},
    "vision": {"zh": "视力情况", "hint": "好 / 一般 / 差"},
    "hearing": {"zh": "听力情况", "hint": "好 / 一般 / 差"},
    "waist_circumference": {"zh": "腰围（厘米）", "hint": "数字，如 82"},
    "hip_circumference": {"zh": "臀围（厘米）", "hint": "数字，如 94"},
    "health_limitation": {"zh": "过去半年健康限制", "hint": "完全没有影响 / 有一点影响 / 影响比较明显 / 影响很大"},
    "badl_bathing": {"zh": "洗澡", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "badl_dressing": {"zh": "穿衣", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "badl_toileting": {"zh": "上厕所", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "badl_transferring": {"zh": "室内走动", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "badl_continence": {"zh": "大小便控制", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "badl_eating": {"zh": "吃饭", "hint": "不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙"},
    "iadl_visiting": {"zh": "串门/走亲戚", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_shopping": {"zh": "买东西", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_cooking": {"zh": "做饭", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_laundry": {"zh": "洗衣服", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_walking": {"zh": "走1公里路", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_carrying": {"zh": "提约5斤重的东西", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_crouching": {"zh": "蹲下再站起来", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "iadl_transport": {"zh": "坐公共交通", "hint": "能自己做 / 做起来有点困难 / 现在做不了"},
    "chronic_disease_any": {"zh": "是否有慢性病", "hint": "有 / 没有 / 记不清"},
    "hypertension": {"zh": "高血压", "hint": "是 / 否"},
    "coronary_heart_disease": {"zh": "冠心病", "hint": "是 / 否"},
    "heart_failure": {"zh": "心力衰竭", "hint": "是 / 否"},
    "arrhythmia": {"zh": "心律失常", "hint": "是 / 否"},
    "stroke": {"zh": "中风或脑血管疾病", "hint": "是 / 否"},
    "diabetes": {"zh": "糖尿病", "hint": "是 / 否"},
    "hyperlipidemia": {"zh": "高血脂", "hint": "是 / 否"},
    "thyroid_disease": {"zh": "甲状腺疾病", "hint": "是 / 否"},
    "chronic_lung_disease": {"zh": "慢性肺病", "hint": "是 / 否"},
    "tuberculosis": {"zh": "肺结核", "hint": "是 / 否"},
    "cataract": {"zh": "白内障", "hint": "是 / 否"},
    "glaucoma": {"zh": "青光眼", "hint": "是 / 否"},
    "hearing_impairment": {"zh": "听力障碍", "hint": "是 / 否"},
    "peptic_ulcer": {"zh": "胃肠溃疡", "hint": "是 / 否"},
    "cholecystitis_gallstones": {"zh": "胆囊炎或胆石症", "hint": "是 / 否"},
    "chronic_kidney_disease": {"zh": "慢性肾病", "hint": "是 / 否"},
    "hepatitis": {"zh": "肝炎", "hint": "是 / 否"},
    "chronic_liver_disease": {"zh": "慢性肝病", "hint": "是 / 否"},
    "parkinsons_disease": {"zh": "帕金森病", "hint": "是 / 否"},
    "dementia": {"zh": "痴呆或阿尔茨海默病", "hint": "是 / 否"},
    "epilepsy": {"zh": "癫痫", "hint": "是 / 否"},
    "arthritis": {"zh": "关节炎", "hint": "是 / 否"},
    "rheumatism_rheumatoid": {"zh": "风湿或类风湿", "hint": "是 / 否"},
    "osteoporosis": {"zh": "骨质疏松", "hint": "是 / 否"},
    "pressure_ulcer": {"zh": "褥疮", "hint": "是 / 否"},
    "cancer": {"zh": "癌症或恶性肿瘤", "hint": "是 / 否"},
    "cancer_type": {"zh": "癌症类型", "hint": "文本，如 肺癌"},
    "frailty": {"zh": "衰弱", "hint": "是 / 否"},
    "fall_history": {"zh": "跌倒史", "hint": "是 / 否"},
    "disability": {"zh": "失能", "hint": "是 / 否"},
    "malnutrition": {"zh": "营养不良", "hint": "是 / 否"},
    "other_chronic_note": {"zh": "其他慢性病补充", "hint": "文本补充"},
    "prostate_disease": {"zh": "前列腺疾病", "hint": "是 / 否"},
    "breast_disease": {"zh": "乳腺疾病", "hint": "是 / 否"},
    "uterine_fibroids": {"zh": "子宫肌瘤", "hint": "是 / 否"},
    "cognition_time": {"zh": "日期定向", "hint": "正确 / 错误 / 不知道"},
    "cognition_month": {"zh": "月份定向", "hint": "正确 / 错误 / 不知道"},
    "cognition_season": {"zh": "季节定向", "hint": "正确 / 错误 / 不知道"},
    "cognition_place": {"zh": "地点定向", "hint": "正确 / 错误 / 不知道"},
    "cognition_calc": {"zh": "计算能力", "hint": "列表，3 个值，每个为 正确 / 错误 / 不知道"},
    "depression": {"zh": "抑郁感", "hint": "从不 / 很少 / 有时 / 经常"},
    "anxiety": {"zh": "焦虑感", "hint": "从不 / 很少 / 有时 / 经常"},
    "loneliness": {"zh": "孤独感", "hint": "从不 / 很少 / 有时 / 经常"},
    "smoking": {"zh": "吸烟", "hint": "从不 / 已戒 / 偶尔 / 每天"},
    "drinking": {"zh": "饮酒", "hint": "从不 / 已戒 / 偶尔 / 每天"},
    "exercise": {"zh": "锻炼", "hint": "从不 / 很少 / 有时 / 经常"},
    "sleep_quality": {"zh": "睡眠质量", "hint": "很好 / 好 / 一般 / 差 / 很差"},
    "living_arrangement": {"zh": "居住安排", "hint": "独居 / 和老伴 / 和子女 / 和老伴及子女 / 住养老院"},
    "caregiver": {"zh": "主要照护者", "hint": "子女 / 老伴 / 保姆 / 自己 / 无人 / 其他"},
    "financial_status": {"zh": "经济状况", "hint": "很好 / 好 / 一般 / 差 / 很差"},
    "medical_insurance": {"zh": "医保情况", "hint": "如 城乡居民医保 / 新农合 / 无"},
}

PROFILE_FIELDS: List[str] = list(FIELD_META.keys())

OPTIONAL_PROFILE_FIELDS = {"waist_circumference", "hip_circumference"}

GENDER_CONDITIONAL_FIELDS = {
    "prostate_disease": "男",
    "breast_disease": "女",
    "uterine_fibroids": "女",
}

CHRONIC_BOOLEAN_FIELDS = [
    "hypertension",
    "coronary_heart_disease",
    "heart_failure",
    "arrhythmia",
    "stroke",
    "diabetes",
    "hyperlipidemia",
    "thyroid_disease",
    "chronic_lung_disease",
    "tuberculosis",
    "cataract",
    "glaucoma",
    "hearing_impairment",
    "peptic_ulcer",
    "cholecystitis_gallstones",
    "chronic_kidney_disease",
    "hepatitis",
    "chronic_liver_disease",
    "parkinsons_disease",
    "dementia",
    "epilepsy",
    "arthritis",
    "rheumatism_rheumatoid",
    "osteoporosis",
    "pressure_ulcer",
    "cancer",
    "frailty",
    "fall_history",
    "disability",
    "malnutrition",
    "prostate_disease",
    "breast_disease",
    "uterine_fibroids",
]

CHRONIC_MULTISELECT_ITEMS: List[Dict[str, Any]] = [
    {"key": "hypertension", "label": "高血压"},
    {"key": "coronary_heart_disease", "label": "冠心病"},
    {"key": "heart_failure", "label": "心力衰竭"},
    {"key": "arrhythmia", "label": "心律失常"},
    {"key": "stroke", "label": "中风或脑血管疾病"},
    {"key": "diabetes", "label": "糖尿病"},
    {"key": "hyperlipidemia", "label": "高血脂"},
    {"key": "thyroid_disease", "label": "甲状腺疾病"},
    {"key": "chronic_lung_disease", "label": "慢性支气管炎、肺气肿、哮喘，或肺部慢性病"},
    {"key": "tuberculosis", "label": "肺结核"},
    {"key": "cataract", "label": "白内障"},
    {"key": "glaucoma", "label": "青光眼"},
    {"key": "hearing_impairment", "label": "听力障碍"},
    {"key": "peptic_ulcer", "label": "胃肠溃疡"},
    {"key": "cholecystitis_gallstones", "label": "胆囊炎或胆石症"},
    {"key": "chronic_kidney_disease", "label": "慢性肾病"},
    {"key": "hepatitis", "label": "肝炎"},
    {"key": "chronic_liver_disease", "label": "慢性肝病（肝硬化）"},
    {"key": "parkinsons_disease", "label": "帕金森病"},
    {"key": "dementia", "label": "痴呆或阿尔茨海默病"},
    {"key": "epilepsy", "label": "癫痫"},
    {"key": "arthritis", "label": "关节炎"},
    {"key": "rheumatism_rheumatoid", "label": "风湿或类风湿"},
    {"key": "osteoporosis", "label": "骨质疏松"},
    {"key": "pressure_ulcer", "label": "褥疮"},
    {"key": "cancer", "label": "癌症或恶性肿瘤"},
    {"key": "frailty", "label": "衰弱"},
    {"key": "fall_history", "label": "跌倒史"},
    {"key": "disability", "label": "失能"},
    {"key": "malnutrition", "label": "营养不良"},
    {"key": "prostate_disease", "label": "前列腺疾病（仅男性）", "sex": "男"},
    {"key": "breast_disease", "label": "乳腺疾病（仅女性）", "sex": "女"},
    {"key": "uterine_fibroids", "label": "子宫肌瘤（仅女性）", "sex": "女"},
    {"key": "_other_chronic_note", "label": "其他慢性病（请补充说明）"},
]

QUESTION_GROUPS: List[Dict[str, Any]] = [
    {
        "group_id": "G1",
        "group_name": "基本信息",
        "fields": ["age", "sex", "residence", "education_years", "marital_status"],
        "steps": [
            {
                "id": "g1_basic",
                "kind": "chat",
                "fields": ["age", "sex", "residence", "education_years", "marital_status"],
                "prompt": (
                    "下面先了解一下您的基本情况，都是一些简单的问题，您按实际情况回答就可以。\n\n"
                    "您今年多大年纪了？您是男士还是女士？您现在住的地方属于城市，还是农村？\n"
                    "您以前大概上过几年学？如果不方便按年数说，也可以告诉我是小学、初中、高中，还是更高一些。\n"
                    "您现在的婚姻情况是怎样的？比如在婚、丧偶，或者其他情况。"
                ),
            }
        ],
    },
    {
        "group_id": "G2",
        "group_name": "身体指标",
        "fields": ["weight", "height", "vision", "hearing", "waist_circumference", "hip_circumference"],
        "steps": [
            {
                "id": "g2_body",
                "kind": "chat",
                "fields": ["weight", "height", "vision", "hearing", "waist_circumference", "hip_circumference"],
                "prompt": (
                    "下面再简单了解一下您的身体基本情况。\n\n"
                    "有些如果记不太清，按大概情况说就可以。\n"
                    "您现在体重大概是多少公斤？身高大概是多少厘米？\n"
                    "您现在看东西怎么样？比如看人、看字、看手机，大体还清楚吗？（好/一般/差）\n"
                    "您现在听别人说话怎么样？一般聊天时能听清吗？（好/一般/差）\n"
                    "如果您最近量过的话，也可以补充一下腰围和臀围；如果没有量过，可以先跳过。"
                ),
            }
        ],
    },
    {
        "group_id": "G3",
        "group_name": "健康限制",
        "fields": ["health_limitation"],
        "steps": [
            {
                "id": "g3_health_limitation",
                "kind": "single_choice",
                "field": "health_limitation",
                "prompt": (
                    "接下来想了解一下，过去半年里，您的身体情况有没有影响到平时的日常活动？\n"
                    "比如出门、做家务、上下楼，或者自己照顾自己这些事情。"
                ),
                "options": HEALTH_LIMITATION_OPTIONS,
            }
        ],
    },
    {
        "group_id": "G4",
        "group_name": "日常活动能力 - 基本生活（BADL）",
        "fields": [
            "badl_bathing",
            "badl_dressing",
            "badl_toileting",
            "badl_transferring",
            "badl_continence",
            "badl_eating",
        ],
        "steps": [
            {
                "id": "g4_badl",
                "kind": "matrix_single_choice",
                "fields": [
                    "badl_bathing",
                    "badl_dressing",
                    "badl_toileting",
                    "badl_transferring",
                    "badl_continence",
                    "badl_eating",
                ],
                "prompt": "接下来问一下日常生活的基本动作，每项选一个最符合您现在情况的答案。",
                "options": BADL_OPTIONS,
                "items": [
                    {"key": "badl_bathing", "label": "洗澡"},
                    {"key": "badl_dressing", "label": "穿衣"},
                    {"key": "badl_toileting", "label": "上厕所"},
                    {"key": "badl_transferring", "label": "室内走动（起床、坐椅子这类）"},
                    {"key": "badl_continence", "label": "大小便控制"},
                    {"key": "badl_eating", "label": "吃饭"},
                ],
            }
        ],
    },
    {
        "group_id": "G5",
        "group_name": "日常活动能力 - 工具性活动（IADL）",
        "fields": [
            "iadl_visiting",
            "iadl_shopping",
            "iadl_cooking",
            "iadl_laundry",
            "iadl_walking",
            "iadl_carrying",
            "iadl_crouching",
            "iadl_transport",
        ],
        "steps": [
            {
                "id": "g5_iadl",
                "kind": "matrix_single_choice",
                "fields": [
                    "iadl_visiting",
                    "iadl_shopping",
                    "iadl_cooking",
                    "iadl_laundry",
                    "iadl_walking",
                    "iadl_carrying",
                    "iadl_crouching",
                    "iadl_transport",
                ],
                "prompt": "下面我再了解一下您做一些稍微复杂一点的日常事情方不方便。",
                "options": IADL_OPTIONS,
                "items": [
                    {"key": "iadl_visiting", "label": "串门/走亲戚"},
                    {"key": "iadl_shopping", "label": "买东西"},
                    {"key": "iadl_cooking", "label": "做饭"},
                    {"key": "iadl_laundry", "label": "洗衣服"},
                    {"key": "iadl_walking", "label": "走1公里路"},
                    {"key": "iadl_carrying", "label": "提约5斤重的东西"},
                    {"key": "iadl_crouching", "label": "蹲下再站起来"},
                    {"key": "iadl_transport", "label": "坐公共交通"},
                ],
            }
        ],
    },
    {
        "group_id": "G6",
        "group_name": "慢性病情况",
        "fields": ["chronic_disease_any"] + CHRONIC_BOOLEAN_FIELDS + ["cancer_type", "other_chronic_note"],
        "steps": [
            {
                "id": "g6_any",
                "kind": "single_choice",
                "field": "chronic_disease_any",
                "prompt": "医生以前有没有明确说过，您有慢性病，或者需要长期治疗、长期复查的病？",
                "options": CHRONIC_ANY_OPTIONS,
            },
            {
                "id": "g6_detail",
                "kind": "multi_select",
                "fields": CHRONIC_BOOLEAN_FIELDS,
                "prompt": "下面这些病里，哪些是医生曾经明确诊断过的？可多选。",
                "items": CHRONIC_MULTISELECT_ITEMS,
            },
            {
                "id": "g6_cancer_type",
                "kind": "chat",
                "fields": ["cancer_type"],
                "prompt": "您刚才提到有癌症或恶性肿瘤，方便补充一下大概是什么癌吗？",
            },
            {
                "id": "g6_other_note",
                "kind": "chat",
                "fields": ["other_chronic_note"],
                "prompt": "您还提到了其他慢性病，方便简单补充说明一下吗？",
            },
        ],
    },
    {
        "group_id": "G7",
        "group_name": "认知功能",
        "fields": ["cognition_time", "cognition_month", "cognition_season", "cognition_place", "cognition_calc"],
        "steps": [
            {"id": "g7_time", "kind": "chat", "fields": ["cognition_time"], "prompt": "接下来我想简单了解一下您的记忆和判断情况。您记得今天是几号吗？"},
            {"id": "g7_month", "kind": "chat", "fields": ["cognition_month"], "prompt": "您记得现在是几月份吗？"},
            {"id": "g7_season", "kind": "chat", "fields": ["cognition_season"], "prompt": "您觉得现在是什么季节？"},
            {"id": "g7_place", "kind": "chat", "fields": ["cognition_place"], "prompt": "您现在是在什么地方？比如在家里、医院，还是别的地方？"},
            {"id": "g7_calc_1", "kind": "chat", "fields": ["cognition_calc"], "prompt": "下面我想请您做一道简单的算术题。不着急，您慢慢想。100 减 7 等于多少？"},
            {"id": "g7_calc_2", "kind": "chat", "fields": ["cognition_calc"], "prompt": "那个答案再减 7 呢？"},
            {"id": "g7_calc_3", "kind": "chat", "fields": ["cognition_calc"], "prompt": "再减一次 7 呢？"},
        ],
    },
    {
        "group_id": "G8",
        "group_name": "心理状态",
        "fields": ["depression", "anxiety", "loneliness"],
        "steps": [
            {
                "id": "g8_depression",
                "kind": "single_choice",
                "field": "depression",
                "prompt": "最近两周，您会不会常常觉得心情不太好，或者做什么都提不起劲？",
                "options": FREQUENCY_OPTIONS,
            },
            {
                "id": "g8_anxiety",
                "kind": "single_choice",
                "field": "anxiety",
                "prompt": "最近两周，您会不会常常觉得心里发紧、爱担心，或者总有点不踏实？",
                "options": FREQUENCY_OPTIONS,
            },
            {
                "id": "g8_loneliness",
                "kind": "single_choice",
                "field": "loneliness",
                "prompt": "最近两周，您会不会觉得有点孤单，或者想找个人说说话的时候，身边没人陪？",
                "options": FREQUENCY_OPTIONS,
            },
        ],
    },
    {
        "group_id": "G9",
        "group_name": "生活方式",
        "fields": ["smoking", "drinking", "exercise", "sleep_quality"],
        "steps": [
            {"id": "g9_smoking", "kind": "single_choice", "field": "smoking", "prompt": "您平时吸烟吗？", "options": SMOKING_DRINKING_OPTIONS},
            {"id": "g9_drinking", "kind": "single_choice", "field": "drinking", "prompt": "您平时喝酒吗？", "options": SMOKING_DRINKING_OPTIONS},
            {"id": "g9_exercise", "kind": "single_choice", "field": "exercise", "prompt": "您平时会不会活动活动、锻炼身体？比如散步、做操、打太极这些。", "options": FREQUENCY_OPTIONS},
            {"id": "g9_sleep", "kind": "single_choice", "field": "sleep_quality", "prompt": "您最近的睡眠怎么样？整体来说睡得好不好？", "options": SLEEP_OPTIONS},
        ],
    },
    {
        "group_id": "G10",
        "group_name": "社会支持",
        "fields": ["living_arrangement", "caregiver", "financial_status", "medical_insurance"],
        "steps": [
            {
                "id": "g10_support",
                "kind": "form_card",
                "fields": ["living_arrangement", "caregiver", "financial_status", "medical_insurance"],
                "prompt": "最后了解一下家庭和支持情况。",
                "form_fields": [
                    {"key": "living_arrangement", "label": "您现在主要是和谁一起生活呢？", "type": "select", "options": LIVING_ARRANGEMENT_OPTIONS},
                    {"key": "caregiver", "label": "如果平时身体不舒服，通常主要是谁照顾您呢？", "type": "select", "options": CAREGIVER_OPTIONS},
                    {"key": "financial_status", "label": "您觉得自己目前的经济状况怎么样？", "type": "select", "options": FINANCIAL_OPTIONS},
                    {
                        "key": "medical_insurance",
                        "label": "您现在有医保吗？您知道自己参加的是哪一种医保吗？",
                        "type": "select_or_text",
                        "options": MEDICAL_INSURANCE_OPTIONS,
                        "allow_custom": True,
                        "custom_key": "medical_insurance_custom",
                        "placeholder": "如果选择其他，可在这里补充",
                    },
                ],
            }
        ],
    },
]

QUESTION_GROUP_MAP = {group["group_id"]: group for group in QUESTION_GROUPS}

STEP_INDEX: Dict[str, Dict[str, int]] = {}
FIELD_TO_GROUP: Dict[str, str] = {}
STEP_TO_GROUP: Dict[str, str] = {}

for group_index, group in enumerate(QUESTION_GROUPS):
    STEP_INDEX[group["group_id"]] = {}
    for step_index, step in enumerate(group["steps"]):
        STEP_INDEX[group["group_id"]][step["id"]] = step_index
        STEP_TO_GROUP[step["id"]] = group["group_id"]
    for field in group["fields"]:
        FIELD_TO_GROUP[field] = group["group_id"]


def get_group_by_id(group_id: str) -> Dict[str, Any]:
    return QUESTION_GROUP_MAP[group_id]


def get_step(group_id: str, step_id: str) -> Dict[str, Any]:
    group = get_group_by_id(group_id)
    for step in group["steps"]:
        if step["id"] == step_id:
            return step
    raise KeyError(f"step not found: {group_id}.{step_id}")


def filter_chronic_items_by_sex(sex: str | None) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in CHRONIC_MULTISELECT_ITEMS:
        item_sex = item.get("sex")
        if item_sex and sex and item_sex != sex:
            continue
        items.append(item)
    return items

