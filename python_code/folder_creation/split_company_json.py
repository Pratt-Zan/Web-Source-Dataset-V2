import json
import os
import shutil

# 读取生成的 JSON 文件
json_path = 'C:\\Users\\Pratt\\Desktop\\HKUST-RA\\Database Construction P2\\company_weburl.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 创建主文件夹 company_set
base_dir = 'C:\\Users\\Pratt\\Desktop\\HKUST-RA\\Database Construction P2\\company_set'
if os.path.exists(base_dir):
    shutil.rmtree(base_dir)
os.makedirs(base_dir)

# 将数据分割为 50 份
chunk_size = len(data) // 50
for i in range(1, 51):
    # 创建子文件夹 company_set_i
    subfolder = os.path.join(base_dir, f'company_set_{i}')
    os.makedirs(subfolder)
    
    # 获取当前份的数据
    start_idx = (i - 1) * chunk_size
    if i == 50:
        chunk = data[start_idx:]  # 最后一份包含剩余所有
    else:
        chunk = data[start_idx:start_idx + chunk_size]
    
    # 保存到 company_i.json
    output_file = os.path.join(subfolder, f'company_{i}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunk, f, ensure_ascii=False, indent=2)

print(f"已分割为 50 份，保存在: {base_dir}")
print(f"每份约 {chunk_size} 条记录")