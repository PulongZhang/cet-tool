GRADES = ("A+", "A", "B+", "B", "B-", "C", "D")

GRADE_SCORES = {
    "A+": 100,
    "A": 93,
    "B+": 86,
    "B": 80,
    "B-": 70,
    "C": 60,
    "D": 50,
}

GROUP_MANAGEMENT = "MANAGEMENT"
GROUP_EMPLOYEE_P1_3 = "EMPLOYEE_P1_3"
GROUP_EMPLOYEE_P4_10 = "EMPLOYEE_P4_10"
GROUP_EXCLUDED = "EXCLUDED"

EMPLOYEE_LEVELS_P1_3 = {"P1", "P2", "P3"}
EMPLOYEE_LEVELS_P4_10 = {"P4", "P5", "P6", "P7", "P8", "P9", "P10"}

SEQUENCE_MANAGEMENT = "管理序列"
SEQUENCE_EMPLOYEE = "员工序列"
SEQUENCE_EXCLUDED = "不参与计算序列"

# 评价维度标签
MANAGEMENT_LABELS = {
    "label_1": "工作能力和方法",
    "label_2": "团队业绩和产出",
    "label_3": "个人关键任务",
}
EMPLOYEE_LABELS = {
    "label_1": "产出和质量",
    "label_2": "主动承担",
    "label_3": "易用性和可维护",
}

# 强制使用管理维度的人员列表（无论其原始序列是什么）
# 这些员工的考核维度锁死为管理序列的三个维度
FORCE_MANAGEMENT_DIMENSIONS_EMPLOYEES = {
    "000825",  # 黄俊
    "001663",  # 丁晓晨
    "001653",  # 何其晓
    "000204",  # 吴军强
}
