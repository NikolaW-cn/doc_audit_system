import os
import sys

# --- 路径配置 (确保能找到 core 文件夹) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from core.pdf_md import PdfMdConverter

def test_real_pdf_conversion():
    # ================= 配置区域 =================
    # 👉 请在这里修改你要测试的文件名 (确保文件在 input 文件夹下)
    target_pdf_name = "test.pdf" 
    # ===========================================

    # 路径设置
    input_dir = os.path.join(project_root, 'input')
    output_dir = os.path.join(project_root, 'output')
    
    # 原始文件路径
    source_pdf_path = os.path.join(input_dir, target_pdf_name)
    
    # 检查文件是否存在
    if not os.path.exists(source_pdf_path):
        print(f"❌ 错误：在 input 文件夹里找不到文件 '{target_pdf_name}'")
        print(f"   请将你的 PDF 文件放入: {input_dir}")
        return

    converter = PdfMdConverter()

    print(f"=== 开始真实文档测试: {target_pdf_name} ===")
    
    # --- 第一步：PDF -> Markdown ---
    # 输出文件名：原文件名_converted.md
    md_filename = f"{os.path.splitext(target_pdf_name)[0]}_converted.md"
    md_output_path = os.path.join(output_dir, md_filename)
    
    print(f"\n[1/2] 正在将 PDF 转换为 Markdown...")
    success_pdf_md = converter.pdf_to_markdown(source_pdf_path, md_output_path)
    
    if not success_pdf_md:
        print("❌ 第一步转换失败，程序终止。")
        return

    # --- 第二步：Markdown -> PDF ---
    # 输出文件名：原文件名_restored.pdf
    pdf_filename = f"{os.path.splitext(target_pdf_name)[0]}_restored.pdf"
    pdf_output_path = os.path.join(output_dir, pdf_filename)

    print(f"\n[2/2] 正在将 Markdown 还原回 PDF...")
    success_md_pdf = converter.markdown_to_pdf(md_output_path, pdf_output_path)

    if success_md_pdf:
        print("\n=== 🎉 转换闭环完成！ ===")
        print(f"📂 原始文件: input/{target_pdf_name}")
        print(f"📄 中间文件: output/{md_filename} (请检查内容是否丢失)")
        print(f"📄 最终文件: output/{pdf_filename} (请检查排版是否还原)")
    else:
        print("❌ 第二步转换失败。")

if __name__ == "__main__":
    test_real_pdf_conversion()