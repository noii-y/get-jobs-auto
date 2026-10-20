"""猎聘（liepin.com）自动化投递Runner"""
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.core.runner_base import BaseRunner
from app.core.browser import browser_manager
from app.core import observability as obs
from app.core.observability import ReasonCode, LoginState
from app.services.ai_service import ai_service
from app.services.blacklist import BlacklistService
from app.services.company_check import company_check_service
from app.database import SessionLocal
from app.models import JobResult, Blacklist


class LiepinRunner(BaseRunner):
    """猎聘自动化投递（打招呼/立即沟通）"""

    platform = "liepin"

    # 猎聘城市代码
    CITY_CODES = {
        "北京": "010", "上海": "020", "广州": "050020",
        "深圳": "050090", "杭州": "070020", "南京": "060020",
        "成都": "280020", "武汉": "170020", "西安": "290020",
        "苏州": "060040", "天津": "030", "重庆": "040",
        "长沙": "180020", "青岛": "100040", "郑州": "150020",
        "全国": "000",
    }

    def __init__(self, run_id: int, config: Dict[str, Any]):
        super().__init__(run_id, config)
        self.keyword = config.get("keyword", "Python开发")
        self.city = config.get("city", "全国")
        self.salary = config.get("salary", "")
        self.max_pages = config.get("max_pages", 5)
        self.default_greeting = config.get("say_hi", "您好，我对这个职位很感兴趣，希望能有机会沟通。")
        self.use_ai = config.get("use_ai", False)
        self.enable_company_check = config.get("enable_company_check", True)
        self.page = None
        self.blacklist_companies = set()

    def _load_blacklist(self):
        """加载黑名单"""
        db = SessionLocal()
        try:
            items = db.query(Blacklist).filter(
                (Blacklist.platform == "liepin") | (Blacklist.platform == "")
            ).all()
            self.blacklist_companies = {item.company_name for item in items}
        finally:
            db.close()

    def check_login(self) -> str:
        """检查猎聘登录状态（三态，检测不到返回 unknown，不再默认 True）"""
        try:
            self.page.get("https://www.liepin.com/zhaopin/")
            time.sleep(3)

            # 风控判定（只检测不绕过）
            try:
                hit, _feat = obs.detect_risk_control(self.page)
                if hit:
                    return LoginState.RISK_CONTROL
            except Exception:
                pass

            # 检查URL是否被重定向到登录页
            if "login" in self.page.url.lower() or "passport" in self.page.url.lower():
                return LoginState.NOT_LOGGED_IN

            # 检查是否有登录弹窗/登录按钮
            login_selectors = [
                "a:contains('登录')", ".login-btn", ".login",
                "[class*='login-btn']", "a[href*='login']",
                ".header-login", ".user-login",
            ]
            for sel in login_selectors:
                try:
                    elem = self.page.ele(sel, timeout=1)
                    if elem and "登录" in elem.text:
                        return LoginState.NOT_LOGGED_IN
                except:
                    continue

            # 检查是否有已登录标志（用户名、消息、我的简历）
            logged_in_selectors = [
                ".user-name", ".username", ".nick-name",
                ".user-center", "a:contains('我的简历')",
                "a[href*='c.liepin.com']", ".header-user",
                ".message-center", "[class*='user-info']",
            ]
            for sel in logged_in_selectors:
                try:
                    elem = self.page.ele(sel, timeout=1)
                    if elem:
                        return LoginState.LOGGED_IN
                except:
                    continue

            # 检查页面是否有职位列表（有列表说明页面正常加载）
            try:
                job_list = self.page.ele("[class*='job-list']", timeout=2)
                if job_list:
                    return LoginState.LOGGED_IN
            except:
                pass

            # 都检测不到时返回 unknown，不再默认 True
            return LoginState.LOGIN_UNKNOWN
        except Exception as e:
            print(f"[liepin] check_login 异常(返回 unknown): {e}")
            return LoginState.LOGIN_UNKNOWN

    async def run(self):
        """执行猎聘投递主流程"""
        await self.log("=" * 50)
        await self.log(f"猎聘投递任务启动")
        await self.log(f"关键词: {self.keyword} | 城市: {self.city} | 最大页数: {self.max_pages}")

        self._load_blacklist()
        await self.log(f"已加载黑名单: {len(self.blacklist_companies)} 家公司")

        try:
            # 连接浏览器（失败记 BROWSER_CONNECT_FAIL）
            try:
                await self.log("正在连接浏览器...")
                self.page = browser_manager.connect(mode="attach")
                await self.log("浏览器连接成功")
            except Exception as e:
                await self.error(f"浏览器连接失败: {e}")
                await self.record_failure(
                    {"title": "(浏览器连接失败)", "company": "liepin"},
                    ReasonCode.BROWSER_CONNECT_FAIL, stage=obs.ErrorStage.CONNECT,
                    exc=e, message=f"浏览器连接失败: {e}", screenshot=True)
                self.fail_reason = ReasonCode.BROWSER_CONNECT_FAIL
                self.error_message = str(e)[:500]
                await self.status("failed", {"reason_code": ReasonCode.BROWSER_CONNECT_FAIL,
                                             "error": str(e)})
                return

            # 检查登录（三态）
            await self.log("检查登录状态...")
            login_state = self.check_login()
            if login_state == LoginState.NOT_LOGGED_IN:
                await self.error("未检测到猎聘登录状态！请先在浏览器中登录猎聘后再运行。")
                self.fail_reason = ReasonCode.NOT_LOGGED_IN
                await self.status("failed", {"reason_code": ReasonCode.NOT_LOGGED_IN,
                                             "reason": "not_logged_in"})
                return
            elif login_state == LoginState.RISK_CONTROL:
                await self.record_failure(
                    {"title": "(风控/安全验证页)", "company": "liepin"},
                    ReasonCode.RISK_CONTROL, stage=obs.ErrorStage.CHECK_LOGIN, screenshot=True)
                await self.error("检测到风控/安全验证页，已停止运行等待人工处理（只检测不绕过）。")
                self.fail_reason = ReasonCode.RISK_CONTROL
                await self.status("failed", {"reason_code": ReasonCode.RISK_CONTROL,
                                             "reason": "risk_control"})
                return
            elif login_state == LoginState.LOGIN_UNKNOWN:
                await self.record_failure(
                    {"title": "(登录态未知)", "company": "liepin"},
                    ReasonCode.LOGIN_UNKNOWN, stage=obs.ErrorStage.CHECK_LOGIN, screenshot=True)
                await self.error("登录状态检测不到，已停止运行，请确认登录状态后重试。")
                self.fail_reason = ReasonCode.LOGIN_UNKNOWN
                await self.status("failed", {"reason_code": ReasonCode.LOGIN_UNKNOWN,
                                             "reason": "login_unknown"})
                return
            await self.log("登录状态正常")

            # 构建搜索URL
            city_code = self.CITY_CODES.get(self.city, "000")
            search_url = f"https://www.liepin.com/zhaopin/?key={self.keyword}&dqs={city_code}"
            if self.salary:
                search_url += f"&salary={self.salary}"

            for page_num in range(1, self.max_pages + 1):
                if self._stopped:
                    await self.log("任务已被用户停止")
                    break
                await self.check_paused()

                await self.log(f"--- 正在处理第 {page_num}/{self.max_pages} 页 ---")
                # 猎聘页码从0开始
                page_url = search_url + f"&curPage={page_num - 1}"
                await self.update_status(action="搜索中", page=page_num)

                try:
                    jobs = await self._get_job_list(page_url)
                    if not jobs:
                        await self.log(f"第 {page_num} 页没有找到职位，结束")
                        await self.record_list_empty(page_url, stage=obs.ErrorStage.LIST)
                        break

                    # 纯观测：记录列表页实际抓到的卡片数（不改流程）
                    self.cards_found = max(self.cards_found, len(jobs))
                    self._persist_run_fields(cards_found=self.cards_found)

                    await self.log(f"第 {page_num} 页找到 {len(jobs)} 个职位")
                    await self.update_status(action="沟通中", page=page_num, total=len(jobs))

                    for idx, job in enumerate(jobs):
                        if self._stopped:
                            break

                        await self.check_paused()
                        self.total_count += 1
                        await self.progress(self.total_count, self.max_pages * 15,
                                            f"第{page_num}页 第{idx+1}/{len(jobs)}个")
                        await self.update_status(
                            action="沟通中", page=page_num, index=idx, total=len(jobs),
                            company=job.get("company", ""), job=job.get("title", "")
                        )

                        # 黑名单检查
                        if job["company"] in self.blacklist_companies:
                            self.skipped_count += 1
                            await self.log(f"跳过黑名单公司: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "黑名单公司")
                            continue

                        # 已投递去重
                        job_url = job.get("job_url", "")
                        if job_url and self._is_already_applied(job_url):
                            self.skipped_count += 1
                            await self.log(f"跳过已投递职位: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "已投递过")
                            continue

                        # 已沟通检查（列表页标识）
                        if job.get("already_contacted"):
                            self.skipped_count += 1
                            await self.log(f"跳过已沟通: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "已沟通过")
                            continue

                        # 公司背调
                        if self.enable_company_check:
                            check_result = company_check_service.check_company(job["company"], job["title"])
                            if check_result["risk_level"] == "high":
                                self.skipped_count += 1
                                keywords = ", ".join([k["keyword"] for k in check_result["matched_keywords"]])
                                await self.log(f"跳过高风险公司({keywords}): {job['company']} - {job['title']}")
                                await self.result(job, "skipped", f"高风险公司: {keywords}")
                                continue
                            elif check_result["risk_level"] == "medium":
                                await self.log(f"⚠ 中风险公司: {job['company']} - {job['title']}")

                        # 投递（打招呼）
                        success = False
                        msg = ""
                        try:
                            success, msg = await self._apply_job(job)
                            if success:
                                self.success_count += 1
                                await self.log(f"✓ 沟通成功: {job['company']} - {job['title']}")
                            else:
                                self.failed_count += 1
                                await self.log(f"✗ 沟通失败: {job['company']} - {job['title']} | {msg}")
                        except Exception as e:
                            self.failed_count += 1
                            msg = str(e)
                            await self.log(f"✗ 沟通异常: {job['company']} - {job['title']} | {msg}")

                        await self.result(job, "success" if success else "failed", msg)
                        self.random_sleep(2.0, 5.0)

                except Exception as e:
                    await self.error(f"第 {page_num} 页处理异常: {str(e)}")
                    continue

            await self.log("=" * 50)
            await self.log(f"投递完成！总计: {self.total_count} | 成功: {self.success_count} | 失败: {self.failed_count} | 跳过: {self.skipped_count}")
            await self.status("completed", self.get_stats())

        except Exception as e:
            await self.error(f"任务执行异常: {str(e)}")
            await self.record_failure(
                {"title": "(任务执行异常)", "company": "liepin"},
                ReasonCode.UNKNOWN, stage=obs.ErrorStage.UNKNOWN,
                exc=e, message=f"任务执行异常: {str(e)}", screenshot=True)
            await self.status("failed", {"error": str(e)})
        finally:
            pass

    async def _get_job_list(self, url: str) -> List[Dict[str, str]]:
        """获取猎聘职位列表（2026新版React页面，用JS获取）"""
        if not self.safe_page_get(url, retries=2):
            await self.log("页面加载失败，尝试重新连接浏览器...")
            if self.reconnect_browser():
                self.safe_page_get(url, retries=2)
            else:
                return []

        # 等待React渲染
        time.sleep(4)

        # 滚动加载更多
        try:
            browser_manager.scroll_down(times=3, delay=0.8)
        except:
            pass
        time.sleep(2)

        # 用JavaScript获取职位卡片（DrissionPage不支持[class*=]属性选择器）
        try:
            js_result = self.page.run_js('''
                const cards = document.querySelectorAll('div[class*="job-card-pc-container"]');
                const jobs = [];
                cards.forEach((card, idx) => {
                    if (idx >= 20) return;
                    const text = card.innerText || '';
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                    // 找职位链接
                    let jobUrl = '';
                    const links = card.querySelectorAll('a[href*="/job/"], a[href*="lptjob"]');
                    if (links.length > 0) {
                        jobUrl = links[0].href;
                    }
                    jobs.push({text: text, lines: lines, job_url: jobUrl});
                });
                return jobs;
            ''')
        except Exception as e:
            await self.log(f"JS获取职位列表失败: {e}")
            return []

        if not js_result:
            await self.log("未找到职位列表元素，页面结构可能已变化")
            return []

        await self.log(f"找到 {len(js_result)} 个职位卡片")

        jobs = []
        for item in js_result:
            try:
                lines = item.get("lines", [])
                text = item.get("text", "")
                job_url = item.get("job_url", "")

                if not lines:
                    continue

                title = ""
                company = ""
                salary = ""
                city = ""
                recruiter = ""

                # 职位名：第一行
                if lines:
                    title = lines[0]

                # 解析各字段（注意顺序：先公司，再城市，避免公司名被当作城市）
                for line in lines:
                    # 薪资：包含k/K、元/天、万等
                    if re.search(r'\d+[-~]\d+[kK]|\d+[kK]|\d+元/天|\d+万|面议', line):
                        if not salary:
                            salary = line
                    # 公司名：包含公司/集团/有限/科技等关键词（优先匹配）
                    elif re.search(r'公司|集团|有限|科技|咨询|网络|信息|文化|传媒|教育|金融|医疗|制造|贸易|服务', line):
                        if not company:
                            company = line
                    # 城市：【城市-区域】格式，或纯城市名（不包含公司关键词）
                    elif '【' in line or '】' in line:
                        city = line.replace('【', '').replace('】', '').strip()
                    elif any(c in line for c in self.CITY_CODES.keys()) and len(line) < 15 and not re.search(r'公司|集团|有限|科技', line):
                        if not city:
                            city = line
                    # 招聘者：包含女士/先生/HR/人事等
                    elif re.search(r'女士|先生|HR|人事|招聘|总监|经理', line):
                        if not recruiter:
                            recruiter = line

                # 如果没找到公司名，用排除法（排除薪资、城市、招聘者、职位名、行业信息）
                if not company and len(lines) >= 4:
                    for line in reversed(lines):
                        if (line != salary and line != city and line != recruiter
                                and line != title and len(line) > 3
                                and not re.search(r'人$|轮|融资|规模|行业|经验|学历|实习|本科|大专|硕士', line)):
                            company = line
                            break

                if not title:
                    continue

                # 检测是否已沟通
                already_contacted = "已沟通" in text or "已联系" in text or "继续沟通" in text

                jobs.append({
                    "title": title,
                    "company": company,
                    "salary": salary,
                    "city": city,
                    "recruiter": recruiter,
                    "job_url": job_url,
                    "already_contacted": already_contacted,
                    "element": None,
                })
            except Exception as e:
                await self.log(f"解析职位卡片异常: {e}")
                continue

        return jobs

    def _safe_text(self, element, selectors: List[str]) -> str:
        """安全地从元素中获取文本，尝试多个选择器"""
        for sel in selectors:
            try:
                ele = element.ele(sel, timeout=1)
                if ele and ele.text:
                    return ele.text.strip()
            except:
                continue
        return ""

    async def _apply_job(self, job: Dict) -> tuple:
        """
        对单个职位进行打招呼/立即沟通
        返回 (success: bool, message: str)
        """
        try:
            # 暂停检查点
            await self.check_paused()

            # 进入职位详情页（优先用URL直接访问，避免新标签页切换问题）
            job_url = job.get("job_url", "")
            if job_url:
                try:
                    self.page.get(job_url)
                    time.sleep(2)
                except:
                    pass
            else:
                # 没有URL时尝试点击卡片
                card = job.get("element")
                if card:
                    try:
                        card.click()
                        time.sleep(2)
                    except:
                        pass

            # 如果打开了新标签页，切换到新标签页（用get_tab方式）
            if len(self.page.tab_ids) > 1:
                try:
                    new_tab = self.page.get_tab(self.page.tab_ids[-1])
                    if new_tab:
                        # 用新标签页操作
                        self.page = new_tab
                except:
                    pass
                time.sleep(1.5)

            # 等待详情页加载
            try:
                self.page.wait.doc_loaded(timeout=10)
            except:
                pass
            time.sleep(2)

            # 查找"聊一聊"按钮（猎聘2026新版沟通按钮文字为"聊一聊"）
            chat_btn = None
            # 优先找主要按钮 .btn-main
            try:
                chat_btn = self.page.ele("a.btn-main", timeout=2)
            except:
                pass

            if not chat_btn:
                # XPath找包含"聊一聊"的a标签
                try:
                    xpath_results = self.page.eles("xpath://a[contains(text(),'聊一聊')]")
                    if xpath_results:
                        chat_btn = xpath_results[0]
                except:
                    pass

            if not chat_btn:
                # XPath找包含"聊一聊"的button
                try:
                    xpath_results = self.page.eles("xpath://button[contains(text(),'聊一聊')]")
                    if xpath_results:
                        chat_btn = xpath_results[0]
                except:
                    pass

            if not chat_btn:
                # 找 .btn-chat
                try:
                    chat_btn = self.page.ele("a.btn-chat", timeout=2)
                except:
                    pass

            if not chat_btn:
                # 备选选择器
                btn_selectors = [
                    "xpath://button[contains(@class,'ant-btn-primary')]",
                    "xpath://a[contains(@class,'btn-chat')]",
                    "xpath://a[contains(text(),'沟通')]",
                    "xpath://button[contains(text(),'沟通')]",
                ]
                chat_btn = self.safe_find_element(btn_selectors, timeout=3, retries=2)

            if not chat_btn:
                # 可能已经沟通过
                try:
                    if "继续沟通" in self.page.html or "已沟通" in self.page.html or "已联系" in self.page.html or "继续聊" in self.page.html:
                        return False, "已沟通过该职位"
                except:
                    pass
                # 关闭可能打开的标签页
                if len(self.page.tab_ids) > 1:
                    try:
                        self.page.close_tabs(self.page.tab_ids[-1])
                    except:
                        pass
                return False, "未找到立即沟通按钮"

            # 点击立即沟通
            try:
                chat_btn.click()
            except:
                try:
                    self.page.run_js("arguments[0].click();", chat_btn)
                except:
                    return False, "沟通按钮点击失败"
            time.sleep(2)

            # 等待对话框/聊天窗口出现
            dialog_selectors = [
                ".chat-dialog", ".dialog-container", ".chat-box",
                "[class*='chat-dialog']", "[class*='dialog']",
                ".im-chat", "[class*='im-chat']",
            ]
            dialog = self.safe_find_element(dialog_selectors, timeout=3, retries=2)

            # 生成打招呼语
            greeting = self.default_greeting
            ai_greeting = ""
            if self.use_ai:
                jd = self._extract_jd()
                ai_greeting = await ai_service.generate_greeting(
                    job_title=job["title"],
                    company=job["company"],
                    jd=jd,
                    user_intro=self.default_greeting
                )
                if ai_greeting:
                    greeting = ai_greeting
                    await self.log(f"  AI打招呼语: {greeting[:50]}...")

            # 输入打招呼语并发送
            if dialog:
                # 检测是否已投递过
                try:
                    if "已发送" in dialog.text or "沟通成功" in dialog.text or "已沟通" in dialog.text:
                        await self.log("  该职位已沟通过，跳过")
                        self._close_and_back()
                        return True, "已沟通过（跳过）"
                except:
                    pass

                # 查找输入框
                input_ele = None
                try:
                    input_ele = dialog.ele("textarea", timeout=2)
                except:
                    pass
                if not input_ele:
                    try:
                        input_ele = dialog.ele("xpath://textarea", timeout=2)
                    except:
                        pass
                if not input_ele:
                    try:
                        input_ele = self.page.ele("textarea.input-area", timeout=2)
                    except:
                        pass

                if input_ele:
                    input_ele.clear()
                    input_ele.input(greeting)
                    time.sleep(0.8)

                    # 查找发送按钮
                    send_btn = None
                    try:
                        send_btn = dialog.ele(".send-message", timeout=2)
                    except:
                        pass
                    if not send_btn:
                        try:
                            send_btn = dialog.ele("xpath://*[contains(@class,'send')]", timeout=2)
                        except:
                            pass
                    if not send_btn:
                        try:
                            send_btn = self.page.ele("[class*='send-btn']", timeout=2)
                        except:
                            pass

                    if send_btn:
                        # 等待按钮可用
                        for _ in range(5):
                            cls = send_btn.attr("class") or ""
                            if "disable" not in cls and "disabled" not in cls:
                                break
                            time.sleep(0.5)
                        send_btn.click()
                        time.sleep(1.5)
                    else:
                        # 按回车发送
                        input_ele.input("\n")
                        time.sleep(1)
                else:
                    await self.log("  未找到输入框，可能已自动发送")
            else:
                await self.log("  未检测到对话框，可能已直接进入聊天页")

            self._close_and_back()
            return True, "打招呼成功"

        except Exception as e:
            # 关闭可能打开的标签页
            if len(self.page.tab_ids) > 1:
                try:
                    self.page.close_tabs(self.page.tab_ids[-1])
                except:
                    pass
            return False, f"异常: {str(e)}"

    def _close_and_back(self):
        """关闭对话框/详情页，返回列表页"""
        try:
            close_btn = self.page.ele(".dialog-container .close", timeout=1)
            if close_btn:
                close_btn.click()
                time.sleep(0.5)
        except:
            pass

        try:
            self.page.back()
            time.sleep(1.5)
        except:
            pass

        if len(self.page.tab_ids) > 1:
            try:
                self.page.close_tabs(self.page.tab_ids[-1])
                time.sleep(0.5)
            except:
                pass

    def _extract_jd(self) -> str:
        """提取职位描述"""
        try:
            jd_selectors = [
                ".job-sec-text", ".job-detail", ".job-description",
                "[class*='job-description']", "[class*='job-detail']",
                ".content", ".job-intro",
            ]
            for sel in jd_selectors:
                try:
                    jd_ele = self.page.ele(sel, timeout=2)
                    if jd_ele:
                        return jd_ele.text[:1000]
                except:
                    continue
        except:
            pass
        return ""

    def _is_already_applied(self, job_url: str) -> bool:
        """检查该职位是否在最近14天内成功投递过"""
        if not job_url:
            return False
        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(days=14)
            existing = db.query(JobResult).filter(
                JobResult.job_url == job_url,
                JobResult.platform == "liepin",
                JobResult.status == "success",
                JobResult.created_at >= cutoff
            ).first()
            return existing is not None
        except Exception as e:
            print(f"查询已投递记录失败: {e}")
            return False
        finally:
            db.close()

    # _save_result 已移至 BaseRunner.result() 统一处理
