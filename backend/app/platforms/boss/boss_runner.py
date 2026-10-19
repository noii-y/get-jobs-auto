"""Boss直聘自动化投递Runner"""
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.runner_base import BaseRunner
from app.core.browser import browser_manager
from app.services.ai_service import ai_service
from app.services.blacklist import BlacklistService
from app.services.company_check import company_check_service
from app.database import SessionLocal
from app.models import JobResult, Blacklist


class BossRunner(BaseRunner):
    """Boss直聘自动化投递"""

    platform = "boss"

    # Boss直聘城市代码映射（常用城市）
    CITY_CODES = {
        "北京": "101010100", "上海": "101020100", "广州": "101280100",
        "深圳": "101280600", "杭州": "101210100", "南京": "101190100",
        "成都": "101270100", "武汉": "101200100", "西安": "101110100",
        "苏州": "101190400", "天津": "101030100", "重庆": "101040100",
        "长沙": "101250100", "青岛": "101120200", "郑州": "101180100",
        "全国": "100010000",
    }

    def __init__(self, run_id: int, config: Dict[str, Any]):
        super().__init__(run_id, config)
        self.keyword = config.get("keyword", "Python开发")
        self.city = config.get("city", "全国")
        self.salary = config.get("salary", "")
        self.experience = config.get("experience", "")
        self.degree = config.get("degree", "")
        self.max_pages = config.get("max_pages", 5)
        self.default_greeting = config.get("say_hi", "您好，我对这个职位很感兴趣，希望能有机会沟通。")
        self.use_ai = config.get("use_ai", False)
        self.filter_inactive_hr = config.get("filter_inactive_hr", True)  # 过滤不活跃HR
        self.hr_active_days = config.get("hr_active_days", 3)  # 只投递N天内活跃的HR
        self.enable_company_check = config.get("enable_company_check", True)  # 公司背调
        self.page = None
        self.blacklist_companies = set()

    def _load_blacklist(self):
        """加载黑名单"""
        db = SessionLocal()
        try:
            items = db.query(Blacklist).filter(
                (Blacklist.platform == "boss") | (Blacklist.platform == "")
            ).all()
            self.blacklist_companies = {item.company_name for item in items}
        finally:
            db.close()

    def _is_hr_active(self, hr_active_text: str) -> bool:
        """
        判断HR是否活跃
        活跃标准：刚刚活跃、今日活跃、N日内活跃（N <= self.hr_active_days）
        如果无法判断（文本为空），默认视为活跃（避免误杀）
        """
        if not hr_active_text or not hr_active_text.strip():
            return True  # 无法判断时默认通过

        text = hr_active_text.strip()

        # 明确活跃的
        if "刚刚活跃" in text or "今日活跃" in text or "在线" in text:
            return True

        # 提取天数
        day_match = re.search(r'(\d+)\s*日?前?活跃', text)
        if day_match:
            days = int(day_match.group(1))
            return days <= self.hr_active_days

        # "活跃于N天前" 格式
        day_match2 = re.search(r'活跃于\s*(\d+)\s*天前', text)
        if day_match2:
            days = int(day_match2.group(1))
            return days <= self.hr_active_days

        # 其他无法识别的格式，默认通过
        return True

    def check_login(self) -> bool:
        """检查Boss直聘登录状态

        检测策略：
        1. 访问职位列表页，等待加载
        2. 检查是否有明确的未登录标志（登录弹窗、登录按钮）
        3. 检查是否有明确的已登录标志（用户头像、消息入口、用户名）
        4. 都检测不到时默认认为已登录（避免误判）
        """
        try:
            self.page.get("https://www.zhipin.com/web/geek/jobs")
            time.sleep(3)

            # 1. 检查URL是否被重定向到登录页
            if "login" in self.page.url.lower():
                return False

            # 2. 检查是否有登录弹窗（未登录时访问职位页会弹出登录框）
            login_popup_selectors = [
                ".sign-pwd",          # 密码登录表单
                ".sign-form",         # 登录表单
                ".login-dialog",      # 登录弹窗
                ".modal-login",       # 登录模态框
                "div[class*='login']", # 包含login的div
            ]
            for selector in login_popup_selectors:
                try:
                    elem = self.page.ele(selector, timeout=1)
                    if elem:
                        return False
                except Exception:
                    continue

            # 3. 检查是否有登录按钮（未登录时导航栏有登录/注册按钮）
            login_btn_selectors = [
                "a[href*='login']",     # 登录链接
                ".nav-login",           # 导航栏登录按钮
                ".btn-login",           # 登录按钮
                "a:contains('登录')",   # 包含登录文字的链接
            ]
            for selector in login_btn_selectors:
                try:
                    elem = self.page.ele(selector, timeout=1)
                    if elem:
                        return False
                except Exception:
                    continue

            # 4. 检查是否有已登录标志（用户头像、消息中心、用户名）
            logged_in_selectors = [
                ".user-avatar",         # 用户头像
                ".nav-msg",             # 消息导航
                ".nav-chat",            # 聊天入口
                ".name",                # 用户名
                ".user-center",         # 用户中心
                "a[href*='geek/job']",  # 职位管理入口（登录后才有）
            ]
            for selector in logged_in_selectors:
                try:
                    elem = self.page.ele(selector, timeout=1)
                    if elem:
                        return True
                except Exception:
                    continue

            # 5. 都检测不到时，检查页面是否正常加载（有职位列表说明已登录或可浏览）
            try:
                job_list = self.page.ele(".job-list-box", timeout=2)
                if job_list:
                    return True
            except Exception:
                pass

            # 6. 最后默认认为已登录（避免误判导致无法使用）
            return True

        except Exception as e:
            await_log = f"检查登录状态失败: {e}"
            # 检测异常时默认返回True，避免因页面结构变化导致完全无法使用
            return True

    async def run(self):
        """执行Boss直聘投递主流程"""
        await self.log("=" * 50)
        await self.log(f"Boss直聘投递任务启动")
        await self.log(f"关键词: {self.keyword} | 城市: {self.city} | 最大页数: {self.max_pages}")

        # 加载黑名单
        self._load_blacklist()
        await self.log(f"已加载黑名单: {len(self.blacklist_companies)} 家公司")

        try:
            # 连接浏览器
            await self.log("正在连接浏览器...")
            self.page = browser_manager.connect(mode="attach")
            await self.log("浏览器连接成功")

            # 检查登录
            await self.log("检查登录状态...")
            if not self.check_login():
                await self.error("未检测到Boss直聘登录状态！请先在浏览器中登录Boss直聘后再运行。")
                await self.status("failed", {"reason": "not_logged_in"})
                return

            await self.log("登录状态正常")

            # 构建搜索URL
            city_code = self.CITY_CODES.get(self.city, "100010000")
            search_url = f"https://www.zhipin.com/web/geek/jobs?query={self.keyword}&city={city_code}"
            if self.salary:
                search_url += f"&salary={self.salary}"
            if self.experience:
                search_url += f"&experience={self.experience}"
            if self.degree:
                search_url += f"&degree={self.degree}"

            # 逐页投递
            for page_num in range(1, self.max_pages + 1):
                if self._stopped:
                    await self.log("任务已被用户停止")
                    break
                await self.check_paused()

                await self.log(f"--- 正在处理第 {page_num}/{self.max_pages} 页 ---")
                page_url = search_url + f"&page={page_num}"
                await self.update_status(action="搜索中", page=page_num)

                try:
                    jobs = await self._get_job_list(page_url)
                    if not jobs:
                        await self.log(f"第 {page_num} 页没有找到职位，结束")
                        break

                    await self.log(f"第 {page_num} 页找到 {len(jobs)} 个职位")
                    await self.update_status(action="投递中", page=page_num, total=len(jobs))

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

                        # 检查黑名单
                        if job["company"] in self.blacklist_companies:
                            self.skipped_count += 1
                            await self.log(f"跳过黑名单公司: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "黑名单公司")
                            continue

                        # 检查是否已投递过（基于本地记录去重）
                        job_url = job.get("job_url", "")
                        if job_url and self._is_already_applied(job_url):
                            self.skipped_count += 1
                            await self.log(f"跳过已投递职位: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "已投递过")
                            continue

                        # 检查HR活跃度
                        if self.filter_inactive_hr and not self._is_hr_active(job.get("hr_active", "")):
                            self.skipped_count += 1
                            hr_status = job.get("hr_active", "未知")
                            await self.log(f"跳过不活跃HR({hr_status}): {job['company']} - {job['title']}")
                            await self.result(job, "skipped", f"HR不活跃: {hr_status}")
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
                                await self.log(f"⚠ 中风险公司: {job['company']} - {job['title']} ({check_result['risk_level_label']})")

                        # 投递
                        success = False
                        msg = ""
                        try:
                            success, msg = await self._apply_job(job)
                            if success:
                                self.success_count += 1
                                await self.log(f"✓ 投递成功: {job['company']} - {job['title']}")
                            else:
                                self.failed_count += 1
                                await self.log(f"✗ 投递失败: {job['company']} - {job['title']} | {msg}")
                        except Exception as e:
                            self.failed_count += 1
                            msg = str(e)
                            await self.log(f"✗ 投递异常: {job['company']} - {job['title']} | {msg}")

                        # 保存结果并推送事件
                        await self.result(job, "success" if success else "failed", msg)

                        # 随机延时，避免风控
                        self.random_sleep(2.0, 5.0)

                except Exception as e:
                    await self.error(f"第 {page_num} 页处理异常: {str(e)}")
                    continue

            await self.log("=" * 50)
            await self.log(f"投递完成！总计: {self.total_count} | 成功: {self.success_count} | 失败: {self.failed_count} | 跳过: {self.skipped_count}")
            await self.status("completed", self.get_stats())

        except Exception as e:
            await self.error(f"任务执行异常: {str(e)}")
            await self.status("failed", {"error": str(e)})
        finally:
            # 不关闭浏览器（接管模式）
            pass

    async def _get_job_list(self, url: str) -> List[Dict[str, str]]:
        """获取职位列表（适配Boss直聘2026新版页面结构）"""
        if not self.safe_page_get(url, retries=2):
            await self.log("页面加载失败，尝试重新连接浏览器...")
            if self.reconnect_browser():
                self.safe_page_get(url, retries=2)
            else:
                return []

        time.sleep(1.5)

        # 诊断：输出页面信息
        try:
            await self.log(f"页面URL: {self.page.url}")
        except:
            pass

        # 滚动加载更多
        try:
            browser_manager.scroll_down(times=3, delay=0.8)
        except:
            pass
        time.sleep(1)

        jobs = []
        # Boss直聘2026新版：职位卡片类名是 job-card-wrap
        selectors = [
            ".job-card-wrap",
            ".job-card-wrapper",
            ".job-list-box .job-card",
        ]

        cards = self.safe_find_elements(selectors, retries=2)

        if not cards:
            await self.log("未找到职位列表元素，页面结构可能已变化")
            return []

        await self.log(f"找到 {len(cards)} 个职位卡片")

        for card in cards[:15]:  # 每页最多15个
            try:
                # 职位名：.job-name
                title_ele = card.ele(".job-name", timeout=1)
                title = title_ele.text if title_ele else "未知职位"

                # 公司名：.boss-name（新版把公司名放在boss-name里）
                company_ele = card.ele(".boss-name", timeout=1) or card.ele(".company-name", timeout=1)
                company = company_ele.text if company_ele else "未知公司"

                # 薪资：.job-salary（可能为空）
                salary_ele = card.ele(".job-salary", timeout=1) or card.ele(".salary", timeout=1)
                salary = salary_ele.text if salary_ele else ""

                # 城市：从卡片文本中提取（格式：公司名 北京·海淀区·学院路）
                city = ""
                try:
                    card_text = card.text
                    # 匹配 "城市·区域·地点" 格式
                    city_match = re.search(r'([\u4e00-\u9fa5]+·[\u4e00-\u9fa5]+·[\u4e00-\u9fa5]+)', card_text)
                    if city_match:
                        city = city_match.group(1)
                    else:
                        # 尝试匹配 "城市·区域" 格式
                        city_match2 = re.search(r'([\u4e00-\u9fa5]+·[\u4e00-\u9fa5]+)', card_text)
                        if city_match2:
                            city = city_match2.group(1)
                except:
                    pass

                # 招聘者信息（新版可能没有单独的招聘者字段）
                recruiter = ""

                # HR活跃状态（新版卡片可能没有，默认活跃）
                hr_active = "今日活跃"  # 默认认为活跃

                # 链接：a.job-name 的 href
                link_ele = card.ele("a.job-name", timeout=1) or card.ele("a", timeout=1)
                job_url = link_ele.attr("href") if link_ele else ""
                if job_url and not job_url.startswith("http"):
                    job_url = "https://www.zhipin.com" + job_url

                if not title or title == "未知职位":
                    continue

                jobs.append({
                    "title": title,
                    "company": company,
                    "salary": salary,
                    "city": city,
                    "recruiter": recruiter,
                    "hr_active": hr_active,
                    "job_url": job_url,
                    "element": card
                })
            except Exception as e:
                await self.log(f"解析职位卡片异常: {e}")
                continue

        return jobs

    async def _apply_job(self, job: Dict) -> tuple:
        """
        对单个职位进行投递（打招呼）
        返回 (success: bool, message: str)
        含页面级重试：找不到按钮时刷新详情页重试，最多2次。
        """
        job_url = job.get("job_url", "")
        max_page_retries = 2  # 页面级重试次数

        for page_attempt in range(max_page_retries + 1):
            try:
                # 进入职位详情页：直接访问URL最稳定
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

                # 切换到新标签页（如果打开了新标签）
                if len(self.page.tab_ids) > 1:
                    self.page.activate_tab(self.page.tab_ids[-1])
                    time.sleep(1.5)

                # 等待详情页加载
                try:
                    self.page.wait.doc_loaded()
                except:
                    pass
                time.sleep(2)

                # 检查暂停状态
                await self.check_paused()

                # 查找"立即沟通"按钮（XPath比CSS选择器更可靠）
                chat_btn = None
                try:
                    xpath_results = self.page.eles("xpath://a[contains(text(),'立即沟通')]")
                    if xpath_results:
                        chat_btn = xpath_results[0]
                except:
                    pass

                if not chat_btn:
                    # 备选：CSS选择器
                    btn_selectors = [".btn-startchat", "a.btn-startchat", "[class*='startchat']"]
                    chat_btn = self.safe_find_element(btn_selectors, timeout=3, retries=2)

                if not chat_btn:
                    # 可能已经沟通过
                    try:
                        if "继续沟通" in self.page.html or "已沟通" in self.page.html:
                            self._close_detail_tabs()
                            return False, "已沟通过该职位"
                    except:
                        pass

                    # 页面级重试：刷新页面后重新查找
                    if page_attempt < max_page_retries and not self._stopped:
                        await self.log(f"  未找到按钮，刷新页面重试({page_attempt + 1}/{max_page_retries})...")
                        try:
                            self.page.refresh()
                            time.sleep(3)
                        except:
                            pass
                        continue
                    else:
                        self._close_detail_tabs()
                        return False, "未找到立即沟通按钮"

                # 找到按钮，执行投递
                return await self._do_chat_and_send(chat_btn, job)

            except Exception as e:
                if page_attempt < max_page_retries and not self._stopped:
                    await self.log(f"  投递异常，重试({page_attempt + 1}/{max_page_retries}): {e}")
                    time.sleep(2)
                    continue
                # 关闭可能打开的标签页
                self._close_detail_tabs()
                return False, f"异常: {str(e)}"

        self._close_detail_tabs()
        return False, "未找到立即沟通按钮"

    def _close_detail_tabs(self):
        """关闭详情标签页，回到列表页"""
        try:
            # 关闭对话框
            close_btn = self.page.ele(".dialog-container .close", timeout=1)
            if close_btn:
                close_btn.click()
                time.sleep(0.5)
        except:
            pass
        try:
            self.page.back()
            time.sleep(1)
        except:
            pass
        if len(self.page.tab_ids) > 1:
            try:
                self.page.close_tabs(self.page.tab_ids[-1])
                self.page.activate_tab(self.page.tab_ids[0])
                time.sleep(0.5)
            except:
                pass

    async def _do_chat_and_send(self, chat_btn, job: Dict) -> tuple:
        """点击沟通按钮并发送打招呼语（从_apply_job拆分）"""
        try:
            # 点击立即沟通
            try:
                chat_btn.click()
            except:
                # JS点击兜底
                try:
                    self.page.run_js("arguments[0].click();", chat_btn)
                except:
                    return False, "沟通按钮点击失败"
            time.sleep(2)

            # 检查暂停状态
            await self.check_paused()

            # 等待对话框出现
            dialog_selectors = [".chat-dialog", ".dialog-container", ".chat-box", ".geek-chat-dialog"]
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
                # 检测是否已投递过（对话框中已有"已发送"消息）
                try:
                    if "已发送" in dialog.text or "沟通成功" in dialog.text:
                        await self.log("  该职位已投递过，跳过")
                        self._close_detail_tabs()
                        return True, "已投递过（跳过）"
                except:
                    pass

                # 查找输入框：textarea.input-area
                input_ele = None
                try:
                    input_ele = dialog.ele("textarea.input-area", timeout=2)
                except:
                    pass
                if not input_ele:
                    try:
                        input_ele = dialog.ele("xpath://textarea", timeout=2)
                    except:
                        pass

                if input_ele:
                    input_ele.clear()
                    input_ele.input(greeting)
                    time.sleep(0.8)

                    # 查找发送按钮：div.send-message
                    send_btn = None
                    try:
                        send_btn = dialog.ele(".send-message", timeout=2)
                    except:
                        pass
                    if not send_btn:
                        try:
                            send_btn = dialog.ele("xpath://*[contains(@class,'send-message')]", timeout=2)
                        except:
                            pass

                    if send_btn:
                        # 等待按钮变为可用（移除disable class）
                        for _ in range(5):
                            cls = send_btn.attr("class") or ""
                            if "disable" not in cls:
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
                # 没有对话框，可能直接进入聊天页面了
                await self.log("  未检测到对话框，可能已直接进入聊天页")

            self._close_detail_tabs()
            return True, "打招呼成功"

        except Exception as e:
            self._close_detail_tabs()
            return False, f"发送异常: {str(e)}"

    def _extract_jd(self) -> str:
        """提取职位描述"""
        try:
            jd_ele = self.page.ele(".job-sec-text", timeout=2) or self.page.ele(".job-detail", timeout=2)
            if jd_ele:
                return jd_ele.text[:1000]
        except:
            pass
        return ""

    def _is_already_applied(self, job_url: str) -> bool:
        """检查该职位是否在最近14天内成功投递过（超过两周自动失效，可重新投递）"""
        if not job_url:
            return False
        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(days=14)
            existing = db.query(JobResult).filter(
                JobResult.job_url == job_url,
                JobResult.platform == "boss",
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
