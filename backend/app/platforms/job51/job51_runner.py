"""51job（前程无忧）自动化投递Runner"""
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.core.runner_base import BaseRunner
from app.core.browser import browser_manager
from app.services.company_check import company_check_service
from app.database import SessionLocal
from app.models import JobResult, Blacklist


class Job51Runner(BaseRunner):
    """51job前程无忧自动化投递"""

    platform = "job51"

    # 51job城市代码
    CITY_CODES = {
        "北京": "010000", "上海": "020000", "广州": "030200",
        "深圳": "040000", "杭州": "080200", "南京": "070200",
        "成都": "090200", "武汉": "180200", "西安": "200200",
        "苏州": "070300", "天津": "050000", "重庆": "060000",
        "长沙": "190200", "青岛": "120300", "郑州": "170200",
        "全国": "000000",
    }

    def __init__(self, run_id: int, config: Dict[str, Any]):
        super().__init__(run_id, config)
        self.keyword = config.get("keyword", "Python开发")
        self.city = config.get("city", "全国")
        self.max_pages = config.get("max_pages", 5)
        self.enable_company_check = config.get("enable_company_check", True)
        self.page = None
        self.blacklist_companies = set()
        self.main_tab_id = None  # 记录主标签页ID

    def _load_blacklist(self):
        """加载黑名单"""
        db = SessionLocal()
        try:
            items = db.query(Blacklist).filter(
                (Blacklist.platform == "job51") | (Blacklist.platform == "")
            ).all()
            self.blacklist_companies = {item.company_name for item in items}
        finally:
            db.close()

    def check_login(self) -> bool:
        """检查51job登录状态"""
        try:
            self.page.get("https://we.51job.com/pc/search")
            time.sleep(2)
            # 检查是否有登录按钮
            login_selectors = [".login", "a:contains('登录')", ".login-btn"]
            for sel in login_selectors:
                try:
                    login_btn = self.page.ele(sel, timeout=1)
                    if login_btn and "登录" in login_btn.text:
                        return False
                except:
                    continue
            # 检查是否有用户头像/用户名（已登录标志）
            user_selectors = [".user-name", ".username", ".user-info", ".avatar"]
            for sel in user_selectors:
                try:
                    user_ele = self.page.ele(sel, timeout=1)
                    if user_ele:
                        return True
                except:
                    continue
            # 如果URL中包含login，说明未登录
            if "login" in self.page.url:
                return False
            # 都检测不到时默认认为已登录（避免误判）
            return True
        except:
            # 检测异常时默认返回True，避免因页面结构变化导致完全无法使用
            return True

    def _safe_get(self, url: str, retries: int = 2) -> bool:
        """安全地访问URL，带重试"""
        for attempt in range(retries + 1):
            try:
                self.page.get(url)
                time.sleep(2)
                # 等待页面加载
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
        """执行51job投递主流程"""
        await self.log("=" * 50)
        await self.log(f"51job投递任务启动")
        await self.log(f"关键词: {self.keyword} | 城市: {self.city} | 最大页数: {self.max_pages}")

        self._load_blacklist()
        await self.log(f"已加载黑名单: {len(self.blacklist_companies)} 家公司")

        try:
            await self.log("正在连接浏览器...")
            self.page = browser_manager.connect(mode="attach")
            await self.log("浏览器连接成功")

            # 记录当前标签页为主标签页
            try:
                self.main_tab_id = self.page.tab_id
            except:
                self.main_tab_id = None

            # 检查登录
            if not self.check_login():
                await self.error("未检测到51job登录状态！请先在浏览器中登录51job后再运行。")
                await self.status("failed", {"reason": "not_logged_in"})
                return

            await self.log("登录状态正常")

            # 构建搜索URL
            city_code = self.CITY_CODES.get(self.city, "000000")
            base_url = f"https://we.51job.com/pc/search?keyword={self.keyword}&city={city_code}&searchType=2"

            for page_num in range(1, self.max_pages + 1):
                if self._stopped:
                    await self.log("任务已被用户停止")
                    break
                await self.check_paused()

                await self.log(f"--- 正在处理第 {page_num}/{self.max_pages} 页 ---")
                page_url = base_url + f"&pageNum={page_num}"
                await self.update_status(action="搜索中", page=page_num)

                try:
                    # 确保在主标签页
                    self._ensure_main_tab()

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

                        # 检查是否已投递过（基于本地记录去重）
                        job_url = job.get("job_url", "")
                        if job_url and self._is_already_applied(job_url):
                            self.skipped_count += 1
                            await self.log(f"跳过已投递职位: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "已投递过")
                            continue

                        # 已申请检查（列表页标识）
                        if job.get("already_applied"):
                            self.skipped_count += 1
                            await self.log(f"跳过已申请: {job['company']} - {job['title']}")
                            await self.result(job, "skipped", "已申请过")
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
                    # 确保回到主标签页
                    self._ensure_main_tab()
                    continue

            await self.log("=" * 50)
            await self.log(f"投递完成！总计: {self.total_count} | 成功: {self.success_count} | 失败: {self.failed_count} | 跳过: {self.skipped_count}")
            await self.status("completed", self.get_stats())

        except Exception as e:
            await self.error(f"任务执行异常: {str(e)}")
            await self.status("failed", {"error": str(e)})

    def _ensure_main_tab(self):
        """确保回到主标签页"""
        try:
            if self.main_tab_id and self.main_tab_id in self.page.tab_ids:
                try:
                    self.page.to_tab(self.main_tab_id)
                except:
                    pass
            elif len(self.page.tab_ids) > 0:
                try:
                    self.page.to_tab(self.page.tab_ids[0])
                except:
                    pass
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
        """获取51job职位列表"""
        if not self._safe_get(url):
            await self.log("页面加载失败")
            return []

        # 等待Vue渲染
        time.sleep(3)

        # 滚动加载更多
        try:
            browser_manager.scroll_down(times=3, delay=0.8)
        except:
            pass
        time.sleep(1)

        # 用JavaScript获取职位卡片（DrissionPage不支持[class*=]属性选择器，51job class带哈希前缀）
        try:
            js_result = self.page.run_js('''
                const cards = document.querySelectorAll('div[class*="joblist"] div[class*="item"]');
                const jobs = [];
                cards.forEach((card, idx) => {
                    if (idx >= 20) return;
                    const text = card.innerText || '';
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                    let jobUrl = '';
                    const links = card.querySelectorAll('a[href*="jobs.51job.com"], a[href*="51job.com/job"]');
                    if (links.length > 0) {
                        jobUrl = links[0].href;
                    }
                    jobs.push({text: text, lines: lines, job_url: jobUrl, index: idx});
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

                title = lines[0] if lines else ""
                company = ""
                salary = ""
                city = ""

                for line in lines:
                    if re.search(r'\d+[-~]\d+[千万]|\d+[千万]|面议|\d+-\d+元', line):
                        if not salary:
                            salary = line
                    elif '·' in line or any(c in line for c in ['北京', '上海', '广州', '深圳', '武汉', '杭州', '南京', '成都', '重庆', '西安', '苏州', '天津']):
                        if not city:
                            city = line
                    elif re.search(r'公司|集团|有限|科技|咨询|网络|信息|文化|传媒|教育|金融|医疗|制造|贸易|服务|餐饮|物流|建设|工程|实业|管理', line):
                        if not company:
                            company = line

                if not company and len(lines) >= 4:
                    for line in reversed(lines):
                        if (line != salary and line != city and line != title
                                and len(line) > 3
                                and not re.search(r'今日|活跃|回复|五险|年终|福利|经验|学历|实习|本科|大专', line)):
                            company = line
                            break

                if not title:
                    continue

                already_applied = "已申请" in text or "已投递" in text

                jobs.append({
                    "title": title,
                    "company": company,
                    "salary": salary,
                    "city": city,
                    "recruiter": "",
                    "job_url": job_url,
                    "already_applied": already_applied,
                    "element": None,
                    "index": item.get("index", 0)
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
        """对单个职位进行投递（51job支持列表页直接点击投递按钮）"""
        try:
            # 暂停检查点
            await self.check_paused()

            # 确保在主标签页（搜索页）
            self._ensure_main_tab()

            job_index = job.get("index", 0)

            # 用JS点击对应职位的投递按钮
            try:
                click_result = self.page.run_js(f'''
                    const cards = document.querySelectorAll('div[class*="joblist"] div[class*="item"]');
                    if (cards.length <= {job_index}) return {{success: false, msg: "职位索引超出范围"}};
                    const card = cards[{job_index}];
                    const applyBtn = card.querySelector('button.btn.apply, [class*="btn"][class*="apply"]');
                    if (!applyBtn) return {{success: false, msg: "未找到投递按钮"}};
                    applyBtn.click();
                    return {{success: true, msg: "已点击投递按钮"}};
                ''')
            except Exception as e:
                return False, f"JS点击投递按钮失败: {e}"

            if not click_result.get("success"):
                return False, click_result.get("msg", "投递失败")

            time.sleep(2)

            # 检查是否有登录弹窗（未登录时会弹出登录框）
            try:
                page_text = self.page.run_js('return document.body.innerText')
                if "登录" in page_text and ("密码" in page_text or "验证码" in page_text):
                    return False, "需要登录才能投递"
            except:
                pass

            # 检查是否有确认弹窗
            try:
                confirm_result = self.page.run_js('''
                    const confirmBtns = document.querySelectorAll('.el-button--primary, button:contains("确认"), .confirm-btn, [class*="confirm"]');
                    for (const btn of confirmBtns) {
                        if (btn.innerText && (btn.innerText.includes("确认") || btn.innerText.includes("确定") || btn.innerText.includes("投递"))) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                ''')
                if confirm_result:
                    time.sleep(1)
            except:
                pass

            # 检查投递结果
            try:
                result_text = self.page.run_js('return document.body.innerText')
                if any(kw in result_text for kw in ["投递成功", "申请成功", "已申请", "申请已提交", "投递成功"]):
                    return True, "投递成功"
            except:
                pass

            return True, "已点击投递按钮"

        except Exception as e:
            self._ensure_main_tab()
            return False, f"异常: {str(e)}"

    def _close_detail_tab(self, detail_tab):
        """关闭详情标签页并回到主标签页"""
        try:
            if detail_tab and detail_tab in self.page.tab_ids:
                self.page.close_tabs(detail_tab)
            elif len(self.page.tab_ids) > 1:
                self.page.close_tabs(self.page.tab_ids[-1])
            time.sleep(0.3)
        except:
            pass
        self._ensure_main_tab()

    def _is_already_applied(self, job_url: str) -> bool:
        """检查该职位是否在最近14天内成功投递过（超过两周自动失效，可重新投递）"""
        if not job_url:
            return False
        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(days=14)
            existing = db.query(JobResult).filter(
                JobResult.job_url == job_url,
                JobResult.platform == "job51",
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
