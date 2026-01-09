import os
import PyInstaller.__main__
import rapidocr_onnxruntime

# 1. 自动定位库的安装路径
package_path = os.path.dirname(rapidocr_onnxruntime.__file__)
print(f"📍 RapidOCR 路径: {package_path}")

# 2. 构造资源路径参数 (源路径;目标路径)
add_data_arg = f"{package_path};rapidocr_onnxruntime"

print("⏳ 开始强力打包 (包含 config.yaml 和模型)...")

# 3. 执行打包
PyInstaller.__main__.run([
    'app_gui.py',
    '--name=DocAudit_Tool',
    '--onefile',
    '--windowed',
    '--noconfirm',
    '--clean',
    f'--add-data={add_data_arg}',  # <--- 这行代码解决了您的问题
])

print("\n✅ 打包完成！")