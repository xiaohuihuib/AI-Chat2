#!/usr/bin/env python3
"""
打包脚本 - 使用PyInstaller打包AI-Chat2应用程序
"""
import os
import subprocess
import sys

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 主脚本文件
MAIN_SCRIPT = "main.py"

# 图标文件
ICON_FILE = "favicon.ico"

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "dist")

# 打包命令
PACK_COMMAND = [
    sys.executable,
    "-m", "PyInstaller",
    "--onefile",  # 打包为单个可执行文件
    "--windowed",  # 无控制台窗口
    f"--icon={ICON_FILE}",  # 指定图标文件
    f"--distpath={OUTPUT_DIR}",  # 指定输出目录
    MAIN_SCRIPT  # 主脚本文件
]

def main():
    """执行打包命令"""
    print("开始打包AI-Chat2应用程序...")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"主脚本文件: {MAIN_SCRIPT}")
    print(f"图标文件: {ICON_FILE}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"打包命令: {' '.join(PACK_COMMAND)}")
    
    try:
        # 执行打包命令
        result = subprocess.run(
            PACK_COMMAND,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        # 输出打包过程
        print("\n打包过程输出:")
        print(result.stdout)
        
        if result.stderr:
            print("\n错误输出:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n打包成功！")
            print(f"可执行文件位置: {os.path.join(OUTPUT_DIR, os.path.splitext(MAIN_SCRIPT)[0] + '.exe')}")
        else:
            print("\n打包失败！")
            print(f"返回码: {result.returncode}")
    except Exception as e:
        print(f"打包过程中发生错误: {e}")

if __name__ == "__main__":
    main()
