import os
import sys

# --- 路径配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from core.word_pdf_html import DocToHtmlConverter

def test_step2():
    print(f"=== 开始测试 Step 2: Word/PDF -> HTML ===")
    
    input_dir = os.path.join(project_root, 'input')
    output_dir = os.path.join(project_root, 'output')
    
    converter = DocToHtmlConverter()

    # --- 1. 测试 Word -> HTML ---
    # ⚠️ 请确保 input 文件夹里有一个叫 test.docx 的文件
    docx_name = "test.docx"
    docx_path = os.path.join(input_dir, docx_name)
    html_from_docx = os.path.join(output_dir, "word_result.html")

    if os.path.exists(docx_path):
        converter.word_to_html(docx_path, html_from_docx)
    else:
        print(f"\n⚠️ [跳过 Word 测试] 未找到 input/{docx_name}")
        print("   👉 如果你想测试 Word 转 HTML，请手动放一个 Word 文档进去。")

    # --- 2. 测试 PDF -> HTML ---
    # 我们直接利用 Step 1 可能会用到的 PDF，或者刚才的 test.pdf
    # 这里我们尝试找 "test.pdf"，如果找不到，就找 input 里的第一个 pdf
    pdf_name = "test.pdf"
    pdf_path = os.path.join(input_dir, pdf_name)
    
    # 如果指定的文件不存在，尝试自动搜索一个
    if not os.path.exists(pdf_path):
        files = [f for f in os.listdir(input_dir) if f.endswith('.pdf')]
        if files:
            pdf_path = os.path.join(input_dir, files[0])
            print(f"\nℹ️ 自动选择测试文件: {files[0]}")
    
    html_from_pdf = os.path.join(output_dir, "pdf_result.html")

    if os.path.exists(pdf_path):
        converter.pdf_to_html(pdf_path, html_from_pdf)
    else:
        print(f"\n⚠️ [跳过 PDF 测试] input 文件夹里没有找到任何 PDF 文件。")

    print("\n=== 测试完成 ===")
    print("请去 output 文件夹查看生成的 .html 文件。直接用浏览器打开即可预览效果。")

if __name__ == "__main__":
    test_step2()