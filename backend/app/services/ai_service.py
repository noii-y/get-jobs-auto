"""AI服务 - 生成个性化打招呼语"""
import json
from typing import Optional
import httpx
from app.config import settings


class AIService:
    """AI打招呼语生成服务"""

    def __init__(self):
        self.base_url = ""
        self.api_key = ""
        self.model = "gpt-4o-mini"
        self.enabled = False

    def configure(self, base_url: str, api_key: str, model: str, enabled: bool = True):
        """配置AI服务"""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.enabled = enabled and bool(api_key)

    async def generate_greeting(self, job_title: str, company: str, jd: str,
                                 user_intro: str = "", max_retries: int = 2) -> Optional[str]:
        """
        根据岗位信息生成个性化打招呼语
        返回生成的打招呼语，失败返回None
        """
        if not self.enabled:
            return None

        prompt = f"""你是一个求职助手，请根据以下岗位信息，生成一段50-80字的求职打招呼语。
要求：
1. 语气真诚、专业，不要过于谄媚
2. 结合岗位要求和我的背景，突出匹配点
3. 表达对岗位的兴趣和胜任信心
4. 不要使用模板化套话

岗位名称：{job_title}
公司：{company}
职位描述：{jd[:500]}
我的背景：{user_intro or '有相关工作经验，学习能力强，能快速上手'}

请直接输出打招呼语内容，不要加任何前缀或解释。"""

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 200
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    greeting = data["choices"][0]["message"]["content"].strip()
                    # 清理可能的引号
                    greeting = greeting.strip('"').strip("'").strip()
                    return greeting if greeting else None
            except Exception as e:
                print(f"[AI] 生成打招呼语失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    continue
                return None

        return None


# 全局AI服务实例
ai_service = AIService()
