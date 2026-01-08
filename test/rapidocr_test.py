import os
import sys

# 1. 动态添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 2. 导入 RapidOCR 核心类
from core.rapidocr import RapidOcrConverter

if __name__ == "__main__":
    # ================= 🔧 配置区域 🔧 =================
    # 你的 Poppler 路径
    MY_POPPLER_PATH = r"D:\poppler-25.12.0\Library\bin"
    # =================================================

    print(f"=== 🚀 开始测试 RapidOCR (ONNX版) ===")

    input_dir = os.path.join(project_root, 'input')
    output_dir = os.path.join(project_root, 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    target_file = "scanned.pdf"
    pdf_path = os.path.join(input_dir, target_file)
    output_html = os.path.join(output_dir, "ocr_rapid_result.html")

    if not os.path.exists(pdf_path):
        print(f"❌ 错误：找不到 {pdf_path}")
        sys.exit(1)

    # 3. 实例化
    print("\n⏳ 正在初始化引擎...")
    converter = RapidOcrConverter(poppler_path=MY_POPPLER_PATH)

    print(f"\n⏳ 正在转换: {os.path.basename(pdf_path)}")
    converter.scanned_pdf_to_html(pdf_path, output_html)

    print("\n=== 测试结束 ===")