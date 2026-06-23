"""
主执行脚本：遍历 company_set 下所有 company_set_i 子文件夹，
为每个子文件夹调用 iter_update_url.run_url_discovery() 执行 URL 发现。

使用单个共享浏览器完成所有子文件夹的爬取，避免反复启动关闭浏览器。
"""

import asyncio
import os
import re
import sys
import argparse  # 【新增】导入 argparse 库

from datetime import datetime

# 确保能导入同目录下的 iter_update_url 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from iter_update_url import run_url_discovery


# ========== 配置区域 ==========

# company_set 的根目录
BASE_DIR = r'C:\Users\Pratt\Desktop\HKUST-RA\Database Construction P2\company_set'

# BFS 最大爬取深度（可根据需要统一调整）
MAX_DEPTH = 2

# ==============================


async def main():
    # 【新增】设置命令行参数解析
    parser = argparse.ArgumentParser(description="URL 发现爬虫批量执行脚本")
    parser.add_argument('--set', type=int, default=None, help="指定要运行的 company_set 序号。如果不指定，则运行全部。")
    args = parser.parse_args()
    target_idx = args.set

    # 扫描所有 company_set_i 子文件夹
    subfolders = []
    for entry in os.listdir(BASE_DIR):
        full_path = os.path.join(BASE_DIR, entry)
        if os.path.isdir(full_path):
            match = re.search(r'company_set_(\d+)', entry)
            if match:
                idx = int(match.group(1))
                
                # 【新增】过滤逻辑：如果命令行指定了序号，且当前序号不匹配，则直接跳过
                if target_idx is not None and idx != target_idx:
                    continue
                    
                subfolders.append((idx, full_path))

    if not subfolders:
        if target_idx is not None:
            print(f"[错误] 在 {BASE_DIR} 下未找到 company_set_{target_idx}")
        else:
            print(f"[错误] 在 {BASE_DIR} 下未找到任何 company_set_N 子文件夹")
        return

    # 按序号排序，保证执行顺序一致
    subfolders.sort(key=lambda x: x[0])

    current_month = datetime.now().strftime('%Y%m')
    total_new_all = 0
    success_count = 0
    fail_count = 0

    print("=" * 60)
    print("  开始处理 company_set（URL 发现）")
    # 【新增】打印当前的运行模式提示
    if target_idx is not None:
        print(f"  运行模式: 仅运行 company_set_{target_idx}")
    else:
        print(f"  运行模式: 运行全部 (共 {len(subfolders)} 个子文件夹)")
    print(f"  月份: {current_month}")
    print(f"  爬取深度: {MAX_DEPTH}")
    print("=" * 60)

    # 启动一个共享浏览器，处理完所有子文件夹后再关闭
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for idx, subfolder in subfolders:
            # === 路径构造 ===
            company_json = os.path.join(subfolder, f'company_{idx}.json')

            # URL 输出: company_set_i/json_iter/Company_iter_url_i_YYYYMM.json
            output_url_path = os.path.join(
                subfolder, 'json_iter', f'Company_iter_url_{idx}_{current_month}.json'
            )

            print(f"\n{'=' * 60}")
            print(f"  正在处理: company_set_{idx}")
            print(f"  输入:    {company_json}")
            print(f"  输出:    {output_url_path}")
            print(f"{'=' * 60}")

            # 输入检查
            if not os.path.isfile(company_json):
                print(f"  [跳过] 公司列表文件不存在: {company_json}")
                fail_count += 1
                continue

            try:
                total_new = await run_url_discovery(
                    company_json_path=company_json,
                    output_url_path=output_url_path,
                    max_depth=MAX_DEPTH,
                    browser=browser,
                )
                total_new_all += total_new
                success_count += 1
                print(f"\n  company_set_{idx} 处理完成（新增 {total_new} 个 URL）")
            except Exception as e:
                print(f"\n  [错误] company_set_{idx} 处理失败: {e}")
                fail_count += 1

        await browser.close()

    # 汇总报告
    print(f"\n{'=' * 60}")
    print("  全部任务结束！")
    print(f"  成功: {success_count} / {len(subfolders)}")
    if fail_count > 0:
        print(f"  失败: {fail_count}")
    print(f"  总计发现 URL: {total_new_all}")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())