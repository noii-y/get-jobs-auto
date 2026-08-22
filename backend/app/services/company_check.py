"""公司背调服务 - 基于公开信息的简单版本
通过风险关键词匹配检测高风险公司
"""
import re
from typing import Dict, List, Optional, Tuple
from app.database import SessionLocal
from app.models import GlobalConfig


# 内置风险关键词库
DEFAULT_RISK_KEYWORDS = {
    # 培训贷/诈骗类
    "培训贷": "high",
    "培训费": "high",
    "交钱": "high",
    "押金": "medium",
    "保证金": "medium",
    "贷款": "high",
    "分期": "medium",
    # 外包/劳务派遣类
    "外包": "low",
    "劳务派遣": "low",
    "人力外包": "low",
    # 不靠谱公司特征
    "金融信息服务": "low",
    "投资管理": "low",
    "资产管理": "low",
    "电子商务": "low",
    "文化传媒": "low",
    # 已知风险模式
    "无责底薪": "medium",
    "高薪诚聘": "medium",
    "月入过万": "medium",
    "轻松赚钱": "high",
    "无需经验": "medium",
    "包吃包住": "low",
}

# 风险等级说明
RISK_LEVELS = {
    "high": {"label": "高风险", "color": "red", "score": 3},
    "medium": {"label": "中风险", "color": "orange", "score": 2},
    "low": {"label": "低风险", "color": "yellow", "score": 1},
}


class CompanyCheckService:
    """公司背调服务"""

    def __init__(self):
        self._risk_keywords: Dict[str, str] = {}
        self._loaded = False

    def _load_keywords(self):
        """从数据库加载自定义风险关键词，合并内置关键词"""
        if self._loaded:
            return
        self._risk_keywords = dict(DEFAULT_RISK_KEYWORDS)
        try:
            db = SessionLocal()
            config = db.query(GlobalConfig).filter(GlobalConfig.key == "risk_keywords").first()
            if config and config.value:
                import json
                custom = json.loads(config.value)
                self._risk_keywords.update(custom)
            db.close()
        except Exception as e:
            print(f"[公司背调] 加载自定义关键词失败: {e}")
        self._loaded = True

    def reload(self):
        """重新加载关键词（修改后调用）"""
        self._loaded = False
        self._load_keywords()

    def check_company(self, company_name: str, job_title: str = "") -> Dict:
        """
        检查公司风险
        返回: {risk_level, risk_score, matched_keywords, suggestions}
        """
        self._load_keywords()

        if not company_name:
            return {
                "risk_level": "unknown",
                "risk_score": 0,
                "matched_keywords": [],
                "suggestions": ["公司名称为空，无法检测"],
            }

        text = f"{company_name} {job_title}".lower()
        matched = []
        total_score = 0

        for keyword, level in self._risk_keywords.items():
            if keyword.lower() in text:
                matched.append({
                    "keyword": keyword,
                    "level": level,
                    "level_label": RISK_LEVELS.get(level, {}).get("label", level),
                })
                total_score += RISK_LEVELS.get(level, {}).get("score", 1)

        # 判断风险等级
        if total_score >= 5:
            risk_level = "high"
        elif total_score >= 3:
            risk_level = "medium"
        elif total_score >= 1:
            risk_level = "low"
        else:
            risk_level = "safe"

        # 生成建议
        suggestions = []
        if risk_level == "high":
            suggestions.append("检测到多个高风险关键词，建议谨慎投递或跳过")
            suggestions.append("可通过天眼查/企查查进一步核实公司信息")
        elif risk_level == "medium":
            suggestions.append("存在一定风险特征，建议投递前了解公司背景")
        elif risk_level == "low":
            suggestions.append("有轻微风险特征，可正常投递但保持警惕")
        else:
            suggestions.append("未检测到明显风险关键词")

        return {
            "risk_level": risk_level,
            "risk_level_label": RISK_LEVELS.get(risk_level, {}).get("label", "未知"),
            "risk_score": total_score,
            "matched_keywords": matched,
            "suggestions": suggestions,
        }

    def is_high_risk(self, company_name: str, job_title: str = "", threshold: str = "medium") -> bool:
        """判断是否为高风险公司（达到阈值则返回True）"""
        result = self.check_company(company_name, job_title)
        threshold_score = RISK_LEVELS.get(threshold, {}).get("score", 2)
        return result["risk_score"] >= threshold_score

    def get_custom_keywords(self) -> Dict[str, str]:
        """获取自定义风险关键词"""
        self._load_keywords()
        # 只返回用户自定义的（不在内置库中的）
        return {k: v for k, v in self._risk_keywords.items() if k not in DEFAULT_RISK_KEYWORDS}

    def add_keyword(self, keyword: str, level: str = "medium") -> bool:
        """添加自定义风险关键词"""
        try:
            db = SessionLocal()
            config = db.query(GlobalConfig).filter(GlobalConfig.key == "risk_keywords").first()
            import json
            custom = {}
            if config and config.value:
                custom = json.loads(config.value)
            custom[keyword] = level
            if config:
                config.value = json.dumps(custom, ensure_ascii=False)
            else:
                config = GlobalConfig(key="risk_keywords", value=json.dumps(custom, ensure_ascii=False))
                db.add(config)
            db.commit()
            db.close()
            self.reload()
            return True
        except Exception as e:
            print(f"[公司背调] 添加关键词失败: {e}")
            return False

    def remove_keyword(self, keyword: str) -> bool:
        """删除自定义风险关键词"""
        try:
            db = SessionLocal()
            config = db.query(GlobalConfig).filter(GlobalConfig.key == "risk_keywords").first()
            if not config or not config.value:
                return False
            import json
            custom = json.loads(config.value)
            if keyword in custom:
                del custom[keyword]
                config.value = json.dumps(custom, ensure_ascii=False)
                db.commit()
                self.reload()
                return True
            db.close()
            return False
        except Exception as e:
            print(f"[公司背调] 删除关键词失败: {e}")
            return False

    def get_all_keywords(self) -> List[Dict]:
        """获取所有风险关键词（内置+自定义）"""
        self._load_keywords()
        return [
            {"keyword": k, "level": v, "level_label": RISK_LEVELS.get(v, {}).get("label", v), "custom": k not in DEFAULT_RISK_KEYWORDS}
            for k, v in sorted(self._risk_keywords.items(), key=lambda x: RISK_LEVELS.get(x[1], {}).get("score", 0), reverse=True)
        ]


# 全局单例
company_check_service = CompanyCheckService()
