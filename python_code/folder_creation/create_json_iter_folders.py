import os

# 母文件夹路径
base_dir = 'C:\\Users\\Pratt\\Desktop\\HKUST-RA\\Database Construction P2\\company_set'

# 为每个 company_set_i 文件夹创建 json_iter 子文件夹
for i in range(1, 51):
    subfolder = os.path.join(base_dir, f'company_set_{i}', 'json_iter')
    os.makedirs(subfolder, exist_ok=True)
    print(f"已创建: {subfolder}")

print("\n✅ 完成！所有子文件夹都已创建 json_iter 文件夹")