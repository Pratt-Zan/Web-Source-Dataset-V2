import json
import asyncio
import random
import os
import shutil
from datetime import datetime
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ANSI颜色码
RED = '\033[91m'
END = '\033[0m'
BLUE = '\033[94m'
GREEN = '\033[92m'


def normalize_url(url):
    """自动补全 URL 协议前缀"""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def get_domain(url):
    """获取 URL 的域名，用于同源判断"""
    return urlparse(url).netloc


def is_valid_link(link):
    """过滤掉不需要的链接类型"""
    if not link:
        return False
    if link.startswith(('javascript:', 'mailto:', '#', 'tel:')):
        return False
    if any(link.lower().endswith(ext) for ext in ['.jpg', '.png', '.gif', '.pdf', '.mp4', '.zip', '.exe', '.css', '.doc', '.docx', '.xls', '.xlsx']):
        return False
    return True


def is_permanent_error(error_msg):
    """判断错误是否为永久性错误（无需重试）"""
    permanent_patterns = ["404", "403", "ERR_NAME_NOT_RESOLVED", "ERR_ADDRESS_UNREACHABLE"]
    return any(p in error_msg for p in permanent_patterns)


async def crawl_urls_only(browser, start_url, site_name, max_depth):
    """
    BFS 爬取单个站点，发现所有同域 URL（全量模式，无历史跳过）。
    """
    target_domain = get_domain(start_url)
    visited = set()
    enqueued = set([start_url])
    queue = [(start_url, 0)]

    print(f"\n  开始 URL 发现: {site_name} - {start_url} (最大深度: {max_depth} 层)")

    new_urls = []

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

    while queue:
        # 1. 收集同一深度的所有URL
        current_depth = queue[0][1]
        batch = []
        while queue and queue[0][1] == current_depth:
            url, _ = queue.pop(0)
            if url not in visited:
                visited.add(url)
                batch.append(url)

        if not batch:
            continue
        if current_depth > max_depth:
            break

        print(f"    [深度 {current_depth}] 处理 {len(batch)} 个URL...")

        # 2. 并发处理（每个URL独立context）
        semaphore = asyncio.Semaphore(1)
        discovered_this_batch = set()

        async def process_one(url):
            """每个URL使用独立context"""
            async with semaphore:
                nonlocal new_urls
                print(f"      [爬取] 深度 {current_depth} - {url}")
                new_urls.append(url)

                # 已到最大深度：无需导航，直接记录URL即可
                if current_depth >= max_depth:
                    return

                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                try:

                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    await page.goto(url, wait_until="domcontentloaded", timeout=150000)

                    hrefs = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a')).map(a => a.href);
                    }""")

                    for href in hrefs:
                        if not is_valid_link(href):
                            continue
                        full_url = urljoin(url, href)
                        if get_domain(full_url) == target_domain:
                            clean_url = full_url.split('#')[0]
                            discovered_this_batch.add(clean_url)

                except Exception as e:
                    error_msg = str(e)
                    if "Download is starting" in error_msg:
                        print(f"      {RED}跳过下载文件: {url}{END}")
                    elif "net::ERR_ABORTED" in error_msg:
                        print(f"      {RED}页面中止: {url}{END}")
                    elif "net::ERR_CONNECTION_CLOSED" in error_msg:

                        print(f"      {BLUE}连接被关闭，重试: {url}{END}")

                        try:
                            await asyncio.sleep(1)

                            await page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=150000
                            )

                            hrefs = await page.evaluate("""
                                () => {
                                    return Array.from(
                                        document.querySelectorAll('a')
                                    ).map(a => a.href);
                                }
                            """)

                            for href in hrefs:

                                if not is_valid_link(href):
                                    continue

                                full_url = urljoin(url, href)

                                if get_domain(full_url) == target_domain:
                                    clean_url = full_url.split('#')[0]
                                    discovered_this_batch.add(clean_url)

                            print(f"      {GREEN}重试成功: {url}{END}")

                        except Exception as e2:

                            print(
                                f"      {RED}重试失败，跳过: {url}: "
                                f"{str(e2)[:80]}{END}"
                            )
                    elif "Timeout" in error_msg:
                        print(f"      {BLUE}超时，等待3s后重试: {url}{END}")
                        await asyncio.sleep(3)
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=150000)
                            hrefs = await page.evaluate("""() => {
                                return Array.from(document.querySelectorAll('a')).map(a => a.href);
                            }""")
                            for href in hrefs:
                                if not is_valid_link(href):
                                    continue
                                full_url = urljoin(url, href)
                                if get_domain(full_url) == target_domain:
                                    clean_url = full_url.split('#')[0]
                                    discovered_this_batch.add(clean_url)
                            print(f"      {GREEN}重试成功: {url}{END}")
                        except Exception as e2:
                            print(f"      {RED}重试仍超时，跳过: {url}{END}: {str(e2)[:80]}")
                    elif is_permanent_error(error_msg):
                        print(f"      {RED}永久错误，跳过: {url}{END}: {error_msg}")
                    else:
                        print(f"      {RED}跳过: {url}{END}: {str(e)[:80]}")
                finally:
                    await page.close()

        # 3. 并发调度
        tasks = [process_one(url) for url in batch]
        await asyncio.gather(*tasks)

        # 4. 将新发现的链接入队
        for clean_url in discovered_this_batch:
            if clean_url not in enqueued:
                enqueued.add(clean_url)
                queue.append((clean_url, current_depth + 1))

        await asyncio.sleep(0.1)
    await context.close()
    return new_urls


async def run_url_discovery(company_json_path, output_url_path, max_depth=2, browser=None):
    """
    对单个 company_set 执行完整 URL 发现（不依赖历史，全量输出）。

    Args:
        company_json_path: company_N.json 路径
        output_url_path:   输出路径 (json_iter/Company_iter_url_N_YYYYMM.json)
        max_depth:         BFS 最大爬取深度
        browser:           playwright browser 实例

    Returns:
        发现的 URL 总数
    """
    # 1. 加载公司列表
    try:
        with open(company_json_path, 'r', encoding='utf-8') as f:
            portals = json.load(f)
        print(f"  公司入口列表加载成功: {len(portals)} 个站点")
    except Exception as e:
        print(f"  [错误] 读取公司入口列表失败: {e}")
        return 0

    all_results = {}

    # 浏览器复用逻辑
    own_browser = None
    if browser is None:
        playwright_obj = await async_playwright().start()
        browser = await playwright_obj.chromium.launch(headless=True,args=['--disable-http2'])
        own_browser = (playwright_obj, browser)

    try:
        for portal in portals:
            site_name = portal.get('companyname', 'Unknown')
            base_url = portal.get('weburl', '')

            if not base_url:
                print(f"  [跳过] 空 URL 的公司: {site_name}")
                continue

            full_url = normalize_url(base_url)

            all_results[site_name] = []

            new_urls = await crawl_urls_only(
                browser,
                full_url,
                site_name,
                max_depth
            )

            all_results[site_name] = new_urls
            print(f"  [{site_name}] 完成: 发现 {len(new_urls)} 个 URL")

            # 每个公司处理完实时保存，防止崩溃丢失
            os.makedirs(os.path.dirname(output_url_path), exist_ok=True)
            temp_file = output_url_path + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=4)
            shutil.move(temp_file, output_url_path)

    finally:
        if own_browser is not None:
            pw, bw = own_browser
            try: await bw.close()
            except: pass
            try: await pw.stop()
            except: pass

    # 剔除空列表的公司
    clean_results = {k: v for k, v in all_results.items() if v}
    total_urls = sum(len(urls) for urls in clean_results.values())
    print(f"  URL 结果已保存至: {output_url_path}（共 {total_urls} 个 URL）")
    return total_urls
