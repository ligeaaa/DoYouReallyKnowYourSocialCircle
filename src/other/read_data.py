import os
from other.constant import folder_path

def read_all_files_in_folder(folder_path):
    """
    读取指定文件夹下的所有文件（包括子文件夹中的文件），返回文件的完整路径列表。
    先读取一级子目录，判断是否跳过，再递归读取。
    """
    _, dirs, _ = os.walk(folder_path)
    file_paths = []
    for dir in dirs:
        if dir.startswith("gh_") or dir.startswith("@") or dir.endswith("@openim"):
            continue
        for root, _, files in os.walk(dir):
            for file in files:
                file_paths.append(os.path.join(root, file))
    return file_paths
# 示例用法
if __name__ == "__main__":
    folder = folder_path
    all_files = read_all_files_in_folder(folder)
    for f in all_files:
        print(f)