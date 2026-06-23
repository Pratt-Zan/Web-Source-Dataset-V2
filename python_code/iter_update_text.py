import json
import asyncio
import random
import os
import shutil

# ANSI颜色码
RED = '\033[91m'
END = '\033[0m'
BLUE = '\033[94m'

def normalize_url(url):
    """自动补全 URL 协议前缀"""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def is_permanent_error(error_msg):
    """判断错误是否为永久性错误（无需重试）"""
    permanent_patterns = ["404", "403", "ERR_NAME_NOT_RESOLVED", "ERR_ADDRESS_UNREACHABLE"]
    return any(p in error_msg for p in permanent_patterns)


async def run_text_extraction(url_source_path, output_text_path, browser=None):
    """
    全量文本提取（不依赖历史，完整输出）。

    Args:
        url_source_path:   URL源文件路径 (json_iter/Company_iter_url_N_YYYYMM.json)
        output_text_path:  文本输出路径 (json_iter/Company_iter_full_N_YYYYMM.json)
        browser:           playwright browser 实例
    Returns:
        提取的文本页数
    """
    # 1. 加载 URL 源文件
    if not os.path.exists(url_source_path):
        print(f"  [警告] URL源文件不存在，跳过: {url_source_path}")
        return 0

    try:
        with open(url_source_path, 'r', encoding='utf-8') as f:
            company_urls = json.load(f)
        print(f"  URL源文件加载成功: {len(company_urls)} 个公司")
    except Exception as e:
        print(f"  [错误] 读取URL源文件失败: {e}")
        return 0

    all_results = {}

    # 2. 浏览器复用逻辑
    own_browser = None
    if browser is None:
        from playwright.async_api import async_playwright
        playwright_obj = await async_playwright().start()
        browser = await playwright_obj.chromium.launch(headless=True)
        own_browser = (playwright_obj, browser)

    try:
        for company_name, urls in company_urls.items():
            if not urls:
                continue

            all_results[company_name] = {}
            urls_to_extract = [normalize_url(u) for u in urls]

            print(f"  [{company_name}] 提取 {len(urls_to_extract)} 个URL...")

            # 每个URL使用独立context
            num_pages = 1
            semaphore = asyncio.Semaphore(num_pages)

            async def handle_route(route):
                if route.request.resource_type in ["image", "stylesheet", "media", "font"]:
                    await route.abort()
                else:
                    await route.continue_()

            async def extract_one(url):
                """每个URL使用独立context"""
                async with semaphore:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    await page.route("**/*", handle_route)
                    try:
                        max_retries = 2
                        retry_delays = [2, 4]

                        for attempt in range(max_retries + 1):
                            try:
                                await asyncio.sleep(random.uniform(0.3, 0.8))
                                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                                text = await page.evaluate("() => document.body ? document.body.innerText.trim() : ''")
                                return url, text
                            except Exception as e:
                                error_msg = str(e)
                                if "Download is starting" in error_msg:
                                    print(f"      {RED}跳过下载文件: {url}{END}")
                                    return url, None
                                elif "net::ERR_ABORTED" in error_msg:
                                    print(f"      {RED}页面中止: {url}{END}")
                                    return url, None
                                elif "net::ERR_CONNECTION_CLOSED" in error_msg:
                                    if attempt < max_retries:
                                        wait = retry_delays[attempt]
                                        print(f"      {BLUE}连接被关闭，等待{wait}s后重试: {url}{END}")
                                        await asyncio.sleep(wait)
                                    else:
                                        print(f"      {RED}连接被关闭，重试{max_retries+1}次均失败，跳过: {url}{END}")
                                        return url, None
                                elif is_permanent_error(error_msg):
                                    print(f"      {RED}永久错误，跳过: {url}{END}: {error_msg}")
                                    return url, None
                                elif attempt < max_retries:
                                    wait = retry_delays[attempt]
                                    print(f"      {BLUE}重试 {attempt+1}/{max_retries}: {url} (等待 {wait}s){END}")
                                    await asyncio.sleep(wait)
                                else:
                                    print(f"      {RED}提取失败: {url}{END}: {str(e)[:80]}")
                                    return url, None
                    finally:
                        await context.close()

            tasks = [extract_one(url) for url in urls_to_extract]
            results = await asyncio.gather(*tasks)

            new_count = 0
            for url, text in results:
                if text is not None:
                    all_results[company_name][url] = text
                    new_count += 1

            print(f"  [{company_name}] 完成: 提取 {new_count}/{len(urls_to_extract)} 页")

            # 每个公司处理完实时保存
            os.makedirs(os.path.dirname(output_text_path), exist_ok=True)
            temp_file = output_text_path + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=4)
            shutil.move(temp_file, output_text_path)

    finally:
        if own_browser is not None:
            pw, bw = own_browser
            try: await bw.close()
            except: pass
            try: await pw.stop()
            except: pass

    # 剔除空字典
    clean_results = {k: v for k, v in all_results.items() if v}
    total_pages = sum(len(texts) for texts in clean_results.values())
    print(f"  文本结果已保存至: {output_text_path}（共 {total_pages} 页）")
    return total_pages
