"""
主执行脚本：遍历 company_set 下所有 company_set_i 子文件夹，
为每个子文件夹调用 run_text_extraction() 执行文本提取。

路径构造：URL源文件和输出文件均使用月份命名。
使用单个共享浏览器完成所有子文件夹的文本提取。
"""

import asyncio
import os
import re
import sys
import argparse
from datetime import datetime

# 确保能导入同目录下的 iter_update_text 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from iter_update_text import run_text_extraction


# ========== 配置区域 ==========

# company_set 的根目录
BASE_DIR = r'C:\Users\Pratt\Desktop\HKUST-RA\Database Construction P2\company_set'

# ==============================


async def main():
    # 扫描所有 company_set_i 子文件夹
    subfolders = []
    for entry in os.listdir(BASE_DIR):
        full_path = os.path.join(BASE_DIR, entry)
        if os.path.isdir(full_path):
            match = re.search(r'company_set_(\d+)', entry)
            if match:
                idx = int(match.group(1))
                subfolders.append((idx, full_path))

    if not subfolders:
        print(f"[错误] 在 {BASE_DIR} 下未找到任何 company_set_N 子文件夹")
        return

    # 按序号排序，保证执行顺序一致
    subfolders.sort(key=lambda x: x[0])

    # 使用 argparse 解析 --set 参数 
    parser = argparse.ArgumentParser(description="执行文本提取任务")
    parser.add_argument('--set', type=int, help='指定要运行的 company_set 序号', default=None)
    args = parser.parse_args()

    if args.set is not None:
        target_idx = args.set
        subfolders = [s for s in subfolders if s[0] == target_idx]
        if not subfolders:
            print(f"[错误] 找不到指定的子文件夹 company_set_{target_idx}")
            return

    current_month = datetime.now().strftime('%Y%m')
    total_new_pages_all = 0
    success_count = 0
    fail_count = 0

    print("=" * 60)
    print("  开始批量文本提取 (company_set)")
    print(f"  共 {len(subfolders)} 个子文件夹")
    print(f"  月份: {current_month}")
    print("=" * 60)

    # 启动一个共享浏览器，处理完所有子文件夹后再关闭
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for idx, subfolder in subfolders:
            # === 路径构造 ===

            # URL 源文件: company_set_i/json_iter/Company_iter_url_i_YYYYMM.json
            url_source = os.path.join(
                subfolder, 'json_iter',
                f'Company_iter_url_{idx}_{current_month}.json'
            )

            # 文本输出: company_set_i/json_iter/Company_iter_full_i_YYYYMM.json
            output_text_path = os.path.join(
                subfolder, 'json_iter',
                f'Company_iter_full_{idx}_{current_month}.json'
            )

            print(f"\n{'=' * 60}")
            print(f"  正在处理: company_set_{idx}")
            print(f"  URL 源:  {url_source}")
            print(f"  输出:    {output_text_path}")
            print(f"{'=' * 60}")

            try:
                total_new_pages = await run_text_extraction(
                    url_source_path=url_source,
                    output_text_path=output_text_path,
                    browser=browser,
                )
                total_new_pages_all += total_new_pages
                success_count += 1
                print(f"\n  company_set_{idx} 文本提取完成")
            except Exception as e:
                print(f"\n  [错误] company_set_{idx} 文本提取失败: {e}")
                fail_count += 1

        await browser.close()

    # 汇总报告
    print(f"\n{'=' * 60}")
    print("  全部任务结束！")
    print(f"  成功: {success_count} / {len(subfolders)}")
    if fail_count > 0:
        print(f"  失败: {fail_count}")
    print(f"  总计提取文本页数: {total_new_pages_all}")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
