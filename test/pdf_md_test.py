import os
import sys

# --- 关键修改 1: 让 Python 能找到 core 文件夹 ---
# 获取当前脚本所在目录 (doc_audit_system/test)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (doc_audit_system)
project_root = os.path.dirname(current_dir)
# 将根目录添加到 Python 搜索路径中
sys.path.append(project_root)

# 现在可以正常导入核心模块了 (假设核心文件名叫 pdf_md.py)
from core.pdf_md import PdfMdConverter

def test_step1():
    # 实例化转换器
    converter = PdfMdConverter()
    
    # --- 关键修改 2: 修正 input 和 output 的路径 ---
    # input 在根目录下，不是在 test 目录下
    input_dir = os.path.join(project_root, 'input')
    output_dir = os.path.join(project_root, 'output')

    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # 确保输入目录存在
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)

    print(f"=== 开始测试 Step 1: PDF <-> Markdown ===")
    print(f"📂 项目根目录: {project_root}")

    # --- 场景 A: 生成测试用的 Markdown 文件 ---
    test_md_name = "test_manual.md"
    test_md_path = os.path.join(input_dir, test_md_name)
    
    # 写入一些测试内容
    with open(test_md_path, "w", encoding="utf-8") as f:
        f.write("""# 文档审核测试

这是一个**测试文档**，用于验证 Markdown 到 PDF 的转换效果。

## 1. 列表测试
- 第一点
- 第二点

## 2. 表格测试 (关键)
| 姓名 | 职位 | 状态 |
|------|------|------|
| 张三 | 经理 | 正常 |
| 李四 | 专员 | <span class="highlight">异常</span> |
""")
    print(f"\n[准备] 已生成测试文件: input/{test_md_name}")

    # 1. 测试 Markdown -> PDF
    pdf_output_name = "step1_result.pdf"
    pdf_output_path = os.path.join(output_dir, pdf_output_name)
    
    # 执行转换
    success_md_pdf = converter.markdown_to_pdf(test_md_path, pdf_output_path)
    if not success_md_pdf:
        print("❌ MD -> PDF 测试失败，请检查报错信息。")
        return

    # 2. 测试 PDF -> Markdown
    md_output_name = "step1_result_back.md"
    md_output_path = os.path.join(output_dir, md_output_name)
    
    converter.pdf_to_markdown(pdf_output_path, md_output_path)

    print("\n=== 测试完成 ===")
    print(f"请检查 output 文件夹：\n1. {pdf_output_name} \n2. {md_output_name}")

if __name__ == "__main__":
    test_step1()