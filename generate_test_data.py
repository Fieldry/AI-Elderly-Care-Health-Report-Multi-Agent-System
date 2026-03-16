#!/usr/bin/env python3
"""
生成测试数据脚本
自动创建几个老人的完整评估数据，方便测试家属端
"""

import sys
import os
import json
from pathlib import Path

# 添加 code 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code'))

from memory.user_profile_store import UserProfileStore
from memory.conversation_manager import ConversationManager
from multi_agent_system_v2 import UserProfile

# 测试数据
TEST_ELDERLY = [
    {
        "name": "王奶奶",
        "age": 78,
        "sex": "女",
        "province": "北京",
        "residence": "城市",
        "education_years": 9,
        "marital_status": "丧偶",
        "health_limitation": "有一点",
        "badl_bathing": "能自己来",
        "badl_dressing": "能自己来",
        "badl_toileting": "能自己来",
        "badl_transferring": "能自己来",
        "iadl_shopping": "能做",
        "iadl_cooking": "能做",
        "iadl_housework": "有点困难",
        "iadl_laundry": "有点困难",
        "iadl_money": "能做",
        "iadl_medication": "能做",
        "iadl_phone": "能做",
        "iadl_transport": "有点困难",
        "hypertension": "是",
        "diabetes": "否",
        "heart_disease": "否",
        "stroke": "否",
        "cataract": "是",
        "cancer": "否",
        "arthritis": "是",
        "cognition_orientation": "正确",
        "cognition_calc": ["正确", "正确", "正确"],
        "depression_frequency": "很少",
        "anxiety_frequency": "很少",
        "smoking": "以前有现在没有",
        "drinking": "从不",
        "exercise": "有时",
        "sleep_quality": "一般",
        "weight": 62.5,
        "height": 158.0,
        "vision": "一般",
        "hearing": "好",
        "living_arrangement": "和子女",
        "cohabitants": 2,
        "financial_status": "一般",
        "income": 3000.0,
        "medical_insurance": "是",
        "caregiver": "子女"
    },
    {
        "name": "李爷爷",
        "age": 82,
        "sex": "男",
        "province": "上海",
        "residence": "城市",
        "education_years": 12,
        "marital_status": "已婚",
        "health_limitation": "比较严重",
        "badl_bathing": "需要部分帮助",
        "badl_dressing": "需要部分帮助",
        "badl_toileting": "能自己来",
        "badl_transferring": "需要部分帮助",
        "iadl_shopping": "做不了",
        "iadl_cooking": "做不了",
        "iadl_housework": "做不了",
        "iadl_laundry": "做不了",
        "iadl_money": "有点困难",
        "iadl_medication": "能做",
        "iadl_phone": "能做",
        "iadl_transport": "做不了",
        "hypertension": "是",
        "diabetes": "是",
        "heart_disease": "是",
        "stroke": "否",
        "cataract": "否",
        "cancer": "否",
        "arthritis": "是",
        "cognition_orientation": "正确",
        "cognition_calc": ["正确", "错误", "正确"],
        "depression_frequency": "有时",
        "anxiety_frequency": "有时",
        "smoking": "从不",
        "drinking": "偶尔",
        "exercise": "很少",
        "sleep_quality": "差",
        "weight": 75.0,
        "height": 172.0,
        "vision": "差",
        "hearing": "一般",
        "living_arrangement": "和老伴",
        "cohabitants": 1,
        "financial_status": "好",
        "income": 5000.0,
        "medical_insurance": "是",
        "caregiver": "老伴"
    },
    {
        "name": "张阿姨",
        "age": 75,
        "sex": "女",
        "province": "广东",
        "residence": "农村",
        "education_years": 6,
        "marital_status": "丧偶",
        "health_limitation": "没有",
        "badl_bathing": "能自己来",
        "badl_dressing": "能自己来",
        "badl_toileting": "能自己来",
        "badl_transferring": "能自己来",
        "iadl_shopping": "能做",
        "iadl_cooking": "能做",
        "iadl_housework": "能做",
        "iadl_laundry": "能做",
        "iadl_money": "能做",
        "iadl_medication": "能做",
        "iadl_phone": "能做",
        "iadl_transport": "能做",
        "hypertension": "否",
        "diabetes": "否",
        "heart_disease": "否",
        "stroke": "否",
        "cataract": "否",
        "cancer": "否",
        "arthritis": "否",
        "cognition_orientation": "正确",
        "cognition_calc": ["正确", "正确", "正确"],
        "depression_frequency": "从不",
        "anxiety_frequency": "从不",
        "smoking": "从不",
        "drinking": "从不",
        "exercise": "经常",
        "sleep_quality": "很好",
        "weight": 58.0,
        "height": 155.0,
        "vision": "好",
        "hearing": "好",
        "living_arrangement": "独居",
        "cohabitants": 0,
        "financial_status": "一般",
        "income": 2000.0,
        "medical_insurance": "是",
        "caregiver": "无人"
    }
]

def generate_test_data():
    """生成测试数据"""
    db_path = "/tmp/elderly-care-db/users.db"
    
    print("🔄 正在生成测试数据...")
    
    # 清理旧数据
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    
    store = UserProfileStore(db_path)
    
    for elderly_data in TEST_ELDERLY:
        # 创建用户
        user_id = store.create_user()
        
        # 提取名字（单独处理）
        name = elderly_data.pop('name', '未命名')
        
        # 更新用户画像
        profile_dict = {k: v for k, v in elderly_data.items()}
        store.update_profile(user_id, profile_dict)
        
        # 在数据库中添加名字字段
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile = json_set(profile, '$.name', ?) WHERE user_id = ?", (name, user_id))
        conn.commit()
        conn.close()
        
        print(f"✓ 创建老人: {name} (ID: {user_id})")
        
        # 创建会话
        session_id = store.create_session(user_id)
        print(f"  └─ 会话: {session_id}")
    
    print("\n✅ 测试数据生成完成！")
    print(f"📍 数据库位置: {db_path}")
    print("\n现在可以：")
    print("1. 访问 http://localhost:3001/family/hub")
    print("2. 登录（任意手机号和密码）")
    print("3. 查看生成的老人列表")

if __name__ == "__main__":
    generate_test_data()
