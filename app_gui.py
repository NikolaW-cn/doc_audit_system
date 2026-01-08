import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess

# ================= 核心模块导入区域 =================
# 1. OCR 模块 (优先加载 RapidOCR)
try:
    from core.rapidocr import RapidOcrConverter as OcrConverter
    OCR_ENGINE_NAME = "RapidOCR (极速)"
except ImportError:
    try:
        from core.ocr_pdf_html import OcrConverter
        OCR_ENGINE_NAME = "PaddleOCR (精准)"
    except ImportError:
        OCR_ENGINE_NAME = "未安装"

# 2. 格式转换模块 (Word/PDF/HTML)
try:
    from core.word_pdf_html import DocToHtmlConverter
except ImportError:
    DocToHtmlConverter = None

# 3. Markdown 转换模块 (Markdown <-> PDF)
try:
    from core.pdf_md import PdfMdConverter
except ImportError as e:
    print(f"⚠️ PDF/MD 模块加载失败: {e}")
    PdfMdConverter = None
# ===================================================

class OcrApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"智能文档审计系统 (全功能版)")
        # 调整窗口高度以容纳新控件
        self.root.geometry("820x750")
        
        # --- 路径配置 ---
        self.dev_poppler = r"D:\poppler-25.12.0\Library\bin"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.dist_poppler = os.path.join(base_dir, "poppler", "Library", "bin")

        # --- 变量定义 ---
        self.file_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar() # 新增：输出目录变量
        self.mode_var = tk.StringVar(value="ocr") # 默认选中 OCR
        
        self.init_ui()

    def init_ui(self):
        # === 1. 功能选择区 ===
        frame_mode = tk.LabelFrame(self.root, text="第一步：选择功能模式", padx=10, pady=10)
        frame_mode.pack(fill="x", padx=10, pady=5)

        modes = [
            ("📄 扫描件 OCR -> HTML", "ocr"),
            ("💻 数字 PDF -> HTML", "digital_pdf"),
            ("📝 Word -> HTML", "word"),
            ("⬇️ PDF -> Markdown", "pdf2md"),
            ("⬆️ Markdown -> PDF", "md2pdf")
        ]

        for i, (text, mode) in enumerate(modes):
            rb = tk.Radiobutton(frame_mode, text=text, variable=self.mode_var, value=mode, 
                                command=self.update_file_filter, font=("微软雅黑", 10))
            rb.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        # === 2. 文件选择区 ===
        frame_file = tk.LabelFrame(self.root, text="第二步：选择要处理的文件", padx=10, pady=10)
        frame_file.pack(fill="x", padx=10, pady=5)
        
        self.entry_path = tk.Entry(frame_file, textvariable=self.file_path_var, width=65)
        self.entry_path.pack(side="left", padx=5)
        
        tk.Button(frame_file, text="📂 浏览文件", command=self.select_file).pack(side="left", padx=5)

        # === 3. 保存位置选择区 (新增功能) ===
        frame_out = tk.LabelFrame(self.root, text="第三步：选择保存位置 (可选，默认保存在原文件旁)", padx=10, pady=10)
        frame_out.pack(fill="x", padx=10, pady=5)
        
        self.entry_out = tk.Entry(frame_out, textvariable=self.output_dir_var, width=65)
        self.entry_out.pack(side="left", padx=5)
        
        tk.Button(frame_out, text="📂 选择文件夹", command=self.select_output_dir).pack(side="left", padx=5)

        # === 4. 操作按钮 ===
        frame_btn = tk.Frame(self.root, pady=5)
        frame_btn.pack(fill="x", padx=10)
        
        self.btn_run = tk.Button(frame_btn, text="🚀 开始处理", command=self.start_thread, 
                                 bg="#007bff", fg="white", font=("微软雅黑", 12, "bold"), height=2)
        self.btn_run.pack(fill="x")

        # === 5. 日志区 ===
        frame_log = tk.LabelFrame(self.root, text="运行日志", padx=10, pady=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(frame_log, height=10, state='disabled', font=("Consolas", 10))
        self.log_area.pack(fill="both", expand=True)

    def log(self, msg):
        print(msg) 
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def update_file_filter(self):
        """切换模式时清空路径"""
        self.file_path_var.set("")
        mode = self.mode_var.get()
        self.log(f"ℹ️ 已切换模式: {mode}")

    def select_file(self):
        mode = self.mode_var.get()
        if mode == "word":
            filetypes = [("Word 文档", "*.docx")]
        elif mode == "md2pdf":
            filetypes = [("Markdown 文件", "*.md")]
        else:
            filetypes = [("PDF 文件", "*.pdf")]

        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.file_path_var.set(filename)

    def select_output_dir(self):
        """选择输出文件夹"""
        dirname = filedialog.askdirectory()
        if dirname:
            self.output_dir_var.set(dirname)

    def start_thread(self):
        file_path = self.file_path_var.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("提示", "请先选择有效的文件！")
            return

        self.btn_run.config(state="disabled", text="⏳ 处理中...", bg="#6c757d")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        
        thread = threading.Thread(target=self.run_logic, args=(file_path,))
        thread.daemon = True
        thread.start()

    def run_logic(self, input_path):
        mode = self.mode_var.get()
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        # === 核心逻辑：确定输出目录 ===
        # 1. 优先使用用户选择的目录
        custom_out_dir = self.output_dir_var.get()
        if custom_out_dir and os.path.isdir(custom_out_dir):
            output_dir = custom_out_dir
            self.log(f"📂 使用自定义保存路径: {output_dir}")
        else:
            # 2. 否则使用默认路径 (原文件旁的 output_result)
            output_dir = os.path.join(os.path.dirname(input_path), "output_result")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            self.log(f"📂 使用默认保存路径: {output_dir}")

        try:
            success = False
            self.log(f"🔄 当前模式: {mode}")
            self.log(f"📄 处理文件: {base_name}")

            # ================= 分发逻辑 =================
            
            # --- 1. OCR 模式 ---
            if mode == "ocr":
                if OCR_ENGINE_NAME == "未安装":
                    self.log("❌ 错误: 未找到 OCR 核心模块")
                    return
                poppler = self.dist_poppler if os.path.exists(self.dist_poppler) else self.dev_poppler
                if not os.path.exists(poppler):
                    self.log("❌ 错误: 未找到 Poppler，OCR 无法运行")
                    return
                self.log(f"🚀 引擎: {OCR_ENGINE_NAME}")
                
                output_file = os.path.join(output_dir, f"{base_name}_ocr.html")
                converter = OcrConverter(poppler_path=poppler)
                success = converter.scanned_pdf_to_html(input_path, output_file)

            # --- 2. 数字 PDF 转 HTML ---
            elif mode == "digital_pdf":
                if not DocToHtmlConverter: self.log("❌ 缺失模块"); return
                output_file = os.path.join(output_dir, f"{base_name}_digital.html")
                converter = DocToHtmlConverter()
                success = converter.pdf_to_html(input_path, output_file)

            # --- 3. Word 转 HTML ---
            elif mode == "word":
                if not DocToHtmlConverter: self.log("❌ 缺失模块"); return
                output_file = os.path.join(output_dir, f"{base_name}_word.html")
                converter = DocToHtmlConverter()
                success = converter.word_to_html(input_path, output_file)

            # --- 4. PDF 转 Markdown ---
            elif mode == "pdf2md":
                if not PdfMdConverter: self.log("❌ 缺失模块"); return
                output_file = os.path.join(output_dir, f"{base_name}.md")
                converter = PdfMdConverter()
                success = converter.pdf_to_markdown(input_path, output_file)

            # --- 5. Markdown 转 PDF ---
            elif mode == "md2pdf":
                if not PdfMdConverter: self.log("❌ 缺失模块"); return
                output_file = os.path.join(output_dir, f"{base_name}_restored.pdf")
                converter = PdfMdConverter()
                success = converter.markdown_to_pdf(input_path, output_file)

            # ================= 结果处理 =================
            if success:
                self.log(f"\n🎉 处理成功！")
                self.log(f"💾 已保存至: {output_file}")
                messagebox.showinfo("完成", f"任务完成！\n文件保存在: {output_file}")
                try:
                    # 打开输出文件夹方便查看
                    os.startfile(output_dir)
                except:
                    pass
            else:
                self.log("\n❌ 处理失败，请检查文件或日志。")
                messagebox.showerror("失败", "处理过程中发生错误")

        except Exception as e:
            self.log(f"❌ 发生异常: {e}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal", text="🚀 开始处理", bg="#007bff"))

if __name__ == "__main__":
    root = tk.Tk()
    app = OcrApp(root)
    root.mainloop()