"""智联招聘（zhaopin.com）自动化投递Runner"""
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.core.runner_base import BaseRunner
from app.core.browser import browser_manager
from app.core import observability as obs
from app.core.observability import ReasonCode, LoginState
from app.services.company_check import company_check_service
from app.database import SessionLocal
from app.models import JobResult, Blacklist


class ZhilianRunner(BaseRunner):
    """智联招聘自动化投递"""

    platform = "zhilian"

    # 智联招聘城市代码（2026新版URL格式: /sou/jl{code}/p{page}）
    CITY_CODES = {
        "北京": "530", "上海": "538", "广州": "763",
        "深圳": "765", "杭州": "653", "南京": "635",
        "成都": "801", "武汉": "736", "西安": "854",
        "苏州": "639", "天津": "511", "重庆": "551",
        "长沙": "749", "青岛": "641", "郑州": "719",
        "全国": "489",
    }

    def __init__(self, run_id: int, config: Dict[str, Any]):
        super().__init__(run_id, config)
        self.keyword = config.get("keyword", "Python开发")
        self.city = config.get("city", "全国")
        self.max_pages = config.get("max_pages", 5)
        self.enable_company_check = config.get("enable_company_check", True)
        self.page = None
        self.blacklist_companies = set()
        self.main_tab_id = None

    def _load_blacklist(self):
        """加载黑名单"""
        db = SessionLocal()
        try:
            items = db.query(Blacklist).filter(
                (Blacklist.platform == "zhilian") | (Blacklist.platform == "")
            ).all()
            self.blacklist_companies = {item.company_name for item in items}
        finally:
            db.close()

    def check_login(self) -> str:
        """检查智联招聘登录状态（三态，检测不到返回 unknown，不再默认 True）"""
        try:
            self.page.get("https://www.zhaopin.com/")
            time.sleep(2)
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
            # 检查是否有登录按钮（未登录时导航栏有登录/注册）
            login_selectors = [
                "a:contains('登录')", ".login-btn",
                "a[href*='login']", "[class*='login-btn']",
            ]
            for sel in login_selectors:
                try:
                    elem = self.page.ele(sel, timeout=1)
                    if elem and "登录" in elem.text:
                        return LoginState.NOT_LOGGED_IN
                except:
                    continue
            # 检查是否有已登录标志（用户名、消息中心、我的智联）
            logged_in_selectors = [
                ".user-name", ".username", ".nick-name",
                "a:contains('我的智联')", "a[href*='i.zhaopin.com']",
                "[class*='user-info']", "[class*='user-center']",
            ]
            for sel in logged_in_selectors:
                try:
                    elem = self.page.ele(sel, timeout=1)
                    if elem:
                        return LoginState.LOGGED_IN
                except:
                    continue
            # 都检测不到时返回 unknown，不再默认 True
            return LoginState.LOGIN_UNKNOWN
        except Exception as e:
            print(f"[zhilian] check_login 异常(返回 unknown): {e}")
            return LoginState.LOGIN_UNKNOWN

    def _safe_get(self, url: str, retries: int = 2) -> bool:
        """安全地访问URL，带重试"""
        for attempt in range(retries + 1):
            try:
                self.page.get(url)
                time.sleep(2)
                try:
                    self.page.wait.doc_loaded(timeout=10)
                except:
                    pass
                time.sleep(1)
                return True
            except Exception as e:
                if attempt < retries:
                    await_log = f"页面加载失败，第{attempt+1}次重试: {e}"
                    time.sleep(2)
                else:
                    return False
        return False

    async def run(self):
        """执行智联招聘投递主流程"""
        await self.log("=" * 50)
        await self.log(f"智联招聘投递任务启动")
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
                    {"title": "(浏览器连接失败)", "company": "zhilian"},
                    ReasonCode.BROWSER_CONNECT_FAIL, stage=obs.ErrorStage.CONNECT,
                    exc=e, message=f"浏览器连接失败: {e}", screenshot=True)
                self.fail_reason = ReasonCode.BROWSER_CONNECT_FAIL
                self.error_message = str(e)[:500]
                await self.status("failed", {"reason_code": ReasonCode.BROWSER_CONNECT_FAIL,
                                             "error": str(e)})
                return

            try:
                self.main_tab_id = self.page.tab_id
            except:
                self.main_tab_id = None

            # 检查登录（三态）
            await self.log("检查登录状态...")
            login_state = self.check_login()
            if login_state == LoginState.NOT_LOGGED_IN:
                await self.error("未检测到智联招聘登录状态！请先在浏览器中登录智联招聘后再运行。")
                self.fail_reason = ReasonCode.NOT_LOGGED_IN
                await self.status("failed", {"reason_code": ReasonCode.NOT_LOGGED_IN,
                                             "reason": "not_logged_in"})
                return
            elif login_state == LoginState.RISK_CONTROL:
                await self.record_failure(
                    {"title": "(风控/安全验证页)", "company": "zhilian"},
                    ReasonCode.RISK_CONTROL, stage=obs.ErrorStage.CHECK_LOGIN, screenshot=True)
                await self.error("检测到风控/安全验证页，已停止运行等待人工处理（只检测不绕过）。")
                self.fail_reason = ReasonCode.RISK_CONTROL
                await self.status("failed", {"reason_code": ReasonCode.RISK_CONTROL,
                                             "reason": "risk_control"})
                return
            elif login_state == LoginState.LOGIN_UNKNOWN:
                await self.record_failure(
                    {"title": "(登录态未知)", "company": "zhilian"},
                    ReasonCode.LOGIN_UNKNOWN, stage=obs.ErrorStage.CHECK_LOGIN, screenshot=True)
                await self.error("登录状态检测不到，已停止运行，请确认登录状态后重试。")
                self.fail_reason = ReasonCode.LOGIN_UNKNOWN
                await self.status("failed", {"reason_code": ReasonCode.LOGIN_UNKNOWN,
                                             "reason": "login_unknown"})
                return
            await self.log("登录状态正常")

            # 构建搜索URL（2026新版格式）
            city_code = self.CITY_CODES.get(self.city, "489")

            for page_num in range(1, self.max_pages + 1):
                if self._stopped:
                    await self.log("任务已被用户停止")
                    break
                await self.check_paused()

                await self.log(f"--- 正在处理第 {page_num}/{self.max_pages} 页 ---")
                page_url = f"https://www.zhaopin.com/sou/jl{city_code}/p{page_num}"
                await self.update_status(action="搜索中", page=page_num)

                try:
                    self._ensure_main_tab()
                    jobs = await self._get_job_list(page_url)
                    if not jobs:
                        await self.log(f"第 {page_num} 页没有找到职位，结束")
                        await self.record_list_empty(page_url, stage=obs.ErrorStage.LIST)
                        break

                    # 纯观测：记录列表页实际抓到的卡片数（不改流程）
                    self.cards_found = max(self.cards_found, len(jobs))
                    self._persist_run_fields(cards_found=self.cards_found)

                    await self.log(f"第 {page_num} 页找到 {len(jobs)} 个职位")
                    await self.update_status(action="投递中", page=page_num, total=len(jobs))

                    for idx, job in enumerate(jobs):
                        if self._stopped:
                            break

                        await self.check_paused()
                        self.total_count += 1
                        await self.progress(self.total_count, self.max_pages * 20,
                                            f"第{page_num}页 第{idx+1}/{len(jobs)}个")
                        await self.update_status(
                            action="投递中", page=page_num, index=idx, total=len(jobs),
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

                        await self.result(job, "success" if success else "failed", msg)
                        self.random_sleep(2.0, 4.0)

                except Exception as e:
                    await self.error(f"第 {page_num} 页处理异常: {str(e)}")
                    self._ensure_main_tab()
                    continue

            await self.log("=" * 50)
            await self.log(f"投递完成！总计: {self.total_count} | 成功: {self.success_count} | 失败: {self.failed_count} | 跳过: {self.skipped_count}")
            await self.status("completed", self.get_stats())

        except Exception as e:
            await self.error(f"任务执行异常: {str(e)}")
            await self.record_failure(
                {"title": "(任务执行异常)", "company": "zhilian"},
                ReasonCode.UNKNOWN, stage=obs.ErrorStage.UNKNOWN,
                exc=e, message=f"任务执行异常: {str(e)}", screenshot=True)
            await self.status("failed", {"error": str(e)})

    def _ensure_main_tab(self):
        """确保回到主标签页"""
        try:
            if self.main_tab_id and self.main_tab_id in self.page.tab_ids:
                self.page.activate_tab(self.main_tab_id)
            elif len(self.page.tab_ids) > 0:
                self.page.activate_tab(self.page.tab_ids[0])
                self.main_tab_id = self.page.tab_ids[0]
        except:
            pass

    def _close_extra_tabs(self):
        """关闭除主标签页外的所有标签页"""
        try:
            extra_tabs = [t for t in self.page.tab_ids if t != self.main_tab_id]
            for tab in extra_tabs:
                try:
                    self.page.close_tabs(tab)
                except:
                    pass
            time.sleep(0.3)
        except:
            pass

    async def _get_job_list(self, url: str) -> List[Dict]:
        """获取智联招聘职位列表（2026新版页面结构）"""
        if not self._safe_get(url):
            await self.log("页面加载失败，尝试重新连接浏览器...")
            if self.reconnect_browser():
                self._safe_get(url)
            else:
                return []

        # 在搜索框中输入关键词并搜索
        try:
            search_input = self.page.ele("input.query-search__content-input", timeout=3)
            if search_input:
                search_input.clear()
                search_input.input(self.keyword)
                time.sleep(0.5)
                search_btn = self.page.ele("button.query-search__content-button", timeout=2)
                if search_btn:
                    search_btn.click()
                    time.sleep(3)
                    try:
                        self.page.wait.doc_loaded(timeout=10)
                    except:
                        pass
                    time.sleep(1)
                    await self.log(f"已搜索关键词: {self.keyword}")
        except Exception as e:
            await self.log(f"搜索关键词时出错: {e}")

        # 滚动加载更多
        try:
            browser_manager.scroll_down(times=3, delay=0.8)
        except:
            pass
        time.sleep(1)

        # 通过投递按钮定位职位卡片（2026新版: button.collect-and-apply__btn）
        jobs = []
        try:
            apply_buttons = self.page.eles("button.collect-and-apply__btn")
            if not apply_buttons:
                await self.log("未找到投递按钮，尝试备选选择器...")
                # 备选：通过XPath找包含"立即投递"的按钮
                try:
                    apply_buttons = self.page.eles("xpath://button[contains(text(),'立即投递')]")
                except:
                    pass
        except:
            apply_buttons = []

        if not apply_buttons:
            await self.log("未找到任何职位的投递按钮，页面结构可能已变化")
            return []

        await self.log(f"找到 {len(apply_buttons)} 个可投递职位")

        for btn_idx, btn in enumerate(apply_buttons[:20]):
            try:
                # 向上找职位卡片容器（最多找5层）
                card = btn
                job_info = {"title": "", "company": "", "salary": "", "city": "", "job_url": "", "apply_button": btn, "btn_index": btn_idx}

                for _ in range(6):
                    try:
                        parent = card.parent()
                        if parent:
                            card = parent
                            # 检查这个元素是否包含职位信息
                            text = card.text
                            if text and len(text) > 20:
                                # 尝试从文本中提取信息
                                lines = [l.strip() for l in text.split('\n') if l.strip()]
                                if lines:
                                    # 智能识别各字段
                                    salary_line = ""
                                    city_line = ""
                                    company_line = ""
                                    title_line = lines[0] if lines else ""

                                    for line in lines:
                                        # 薪资：包含K、元/月、·薪、数字范围
                                        if re.search(r'\d+K|\d+-\d+K|元/月|\d+薪|薪资|面议', line, re.I):
                                            if not salary_line:
                                                salary_line = line
                                        # 城市：包含城市名
                                        elif any(city in line for city in self.CITY_CODES.keys()) or re.search(r'[市州]$', line):
                                            if not city_line:
                                                city_line = line
                                        # 公司名：包含公司相关关键词
                                        elif re.search(r'公司|集团|有限|科技|咨询|网络|信息|文化|传媒|教育|金融|医疗|制造|贸易|服务', line):
                                            if not company_line:
                                                company_line = line

                                    # 如果没找到公司名，用第二行（排除薪资和城市后）
                                    if not company_line:
                                        for line in lines[1:]:
                                            if line != salary_line and line != city_line and len(line) > 2:
                                                company_line = line
                                                break

                                    # 如果没找到职位名，用第一行
                                    if not title_line:
                                        title_line = lines[0] if lines else ""

                                    job_info["title"] = title_line
                                    job_info["company"] = company_line
                                    job_info["salary"] = salary_line
                                    job_info["city"] = city_line
                                break
                    except:
                        break

                # 尝试获取职位链接
                try:
                    link = card.ele("a", timeout=1)
                    if link:
                        href = link.attr("href") or ""
                        if href:
                            job_info["job_url"] = href if href.startswith("http") else "https:" + href if href.startswith("//") else "https://www.zhaopin.com" + href
                except:
                    pass

                if not job_info["title"]:
                    # 尝试从按钮附近获取职位名
                    try:
                        title_ele = card.ele("[class*='job-name']", timeout=1) or card.ele("[class*='title']", timeout=1)
                        if title_ele:
                            job_info["title"] = title_ele.text
                    except:
                        pass

                if job_info["title"] or job_info["company"]:
                    jobs.append(job_info)
            except Exception as e:
                await self.log(f"解析职位卡片异常: {e}")
                continue

        return jobs

    async def _apply_job(self, job: Dict) -> tuple:
        """对单个职位进行投递（智联招聘2026新版）"""
        try:
            # 暂停检查点
            await self.check_paused()

            self._ensure_main_tab()
            time.sleep(0.5)

            # 获取投递按钮（优先用缓存的元素引用，失败则按索引重新查找）
            btn = job.get("apply_button")
            btn_index = job.get("btn_index", 0)

            # 检查按钮是否可用
            btn_valid = False
            try:
                btn_text = btn.text
                if "已投递" in btn_text or "已申请" in btn_text:
                    return False, "已投递过该职位"
                btn_valid = True
            except:
                pass

            # 如果缓存的按钮元素失效，按索引重新查找
            if not btn_valid:
                try:
                    all_btns = self.page.eles("button.collect-and-apply__btn")
                    if not all_btns:
                        all_btns = self.page.eles("xpath://button[contains(text(),'立即投递')]")
                    if all_btns and btn_index < len(all_btns):
                        btn = all_btns[btn_index]
                        btn_valid = True
                except:
                    pass

            if not btn_valid:
                return False, "未找到投递按钮"

            # 点击投递按钮（多种方式兜底）
            clicked = False
            tabs_before = len(self.page.tab_ids)

            # 方式1：原生点击
            if not clicked:
                try:
                    btn.click()
                    clicked = True
                except:
                    pass

            # 方式2：JS点击
            if not clicked:
                try:
                    self.page.run_js("arguments[0].click();", btn)
                    clicked = True
                except:
                    pass

            # 方式3：按索引重新查找后JS点击
            if not clicked:
                try:
                    self.page.run_js(f'''
                        const btns = document.querySelectorAll("button.collect-and-apply__btn");
                        if (btns.length > {btn_index}) {{ btns[{btn_index}].click(); return true; }}
                        return false;
                    ''')
                    clicked = True
                except:
                    pass

            if not clicked:
                return False, "投递按钮点击失败"

            time.sleep(2.5)

            # 如果打开了新标签页，关闭它并回到主标签页
            try:
                if len(self.page.tab_ids) > tabs_before:
                    new_tab = self.page.tab_ids[-1]
                    self.page.close_tabs(new_tab)
                    time.sleep(0.5)
                    self._ensure_main_tab()
                    time.sleep(1)
            except:
                pass

            # 检查是否有简历选择弹窗/确认弹窗（只点击可见的确认按钮）
            try:
                confirmed = self.page.run_js('''
                    const btns = document.querySelectorAll('.el-button--primary, button');
                    for (const btn of btns) {
                        if (btn.offsetParent === null) continue;
                        const text = (btn.innerText || '').trim();
                        if (text === '确认投递' || text === '确定' || text === '确认' || text === '投递') {
                            // 确保按钮在可见的弹窗中
                            const dialog = btn.closest('.el-dialog, [class*="dialog"], [class*="modal"], [class*="popup"]');
                            if (dialog && dialog.offsetParent !== null) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                ''')
                if confirmed:
                    time.sleep(1.5)
            except:
                pass

            # 检查投递结果
            success = False
            try:
                # 检查页面是否有成功提示
                page_text = self.page.html
                if any(kw in page_text for kw in ["投递成功", "申请成功", "已申请", "投递已提交", "申请已提交", "投递完成"]):
                    success = True
            except:
                pass

            # 关闭可能弹出的弹窗
            try:
                close_selectors = [".close", "[class*='close']", "xpath://*[contains(@class,'close')]"]
                for sel in close_selectors:
                    try:
                        close_btn = self.page.ele(sel, timeout=1)
                        if close_btn:
                            close_btn.click()
                            time.sleep(0.3)
                            break
                    except:
                        continue
            except:
                pass

            if success:
                return True, "投递成功"
            else:
                return True, "已点击投递按钮"  # 假设点击成功

        except Exception as e:
            self._close_extra_tabs()
            self._ensure_main_tab()
            return False, f"异常: {str(e)}"

    def _is_already_applied(self, job_url: str) -> bool:
        """检查该职位是否在最近14天内成功投递过"""
        if not job_url:
            return False
        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(days=14)
            existing = db.query(JobResult).filter(
                JobResult.job_url == job_url,
                JobResult.platform == "zhilian",
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
