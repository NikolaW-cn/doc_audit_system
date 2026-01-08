import os
import sys

# 1. 动态添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 2. 导入核心类
from core.ocr_pdf_html import OcrConverter

if __name__ == "__main__":
    # ================= 🔧 配置区域 🔧 =================
    # 请填入你之前解压的 Poppler bin 路径
    # 你的路径是: D:\poppler-25.12.0\Library\bin
    MY_POPPLER_PATH = r"D:\poppler-25.12.0\Library\bin"
    # =================================================

    print(f"=== 🚀 开始测试 Step 3 (Hybrid OCR: Poppler + Paddle) ===")
    
    input_dir = os.path.join(project_root, 'input')
    output_dir = os.path.join(project_root, 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    target_file = "scanned.pdf"
    pdf_path = os.path.join(input_dir, target_file)
    if not os.path.exists(pdf_path):
        print(f"ℹ️ 未找到 {target_file}，使用 test.pdf")
        pdf_path = os.path.join(input_dir, "test.pdf")

    if not os.path.exists(pdf_path):
        print(f"❌ 错误：input 文件夹为空")
        sys.exit(1)

    output_html = os.path.join(output_dir, "ocr_final_result.html")

    # 3. 实例化 (传入 Poppler 路径)
    print("\n⏳ 正在初始化引擎...")
    converter = OcrConverter(poppler_path=MY_POPPLER_PATH)
    
    print(f"\n⏳ 正在转换: {os.path.basename(pdf_path)}")
    print("   (这步分为：转图片 -> OCR识别，请耐心等待...)")
    converter.scanned_pdf_to_html(pdf_path, output_html)

    print("\n=== 测试结束 ===")