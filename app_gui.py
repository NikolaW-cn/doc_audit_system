import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
# ... (上面的 import os, sys 等保持不变) ...
import subprocess

# ========================================================
# 🛑 核心修复：防止 Poppler/OCR 调用时弹出黑窗口 (隐身补丁)
# ========================================================
if sys.platform == "win32":
    # 备份原始的 Popen 类
    _original_Popen = subprocess.Popen

    class NoWindowPopen(_original_Popen):
        def __init__(self, *args, **kwargs):
            # 定义“隐藏窗口”的配置
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # 强制应用这个配置
            kwargs['startupinfo'] = startupinfo
            
            # 调用原始的 Popen
            super().__init__(*args, **kwargs)

    # 用我们的“隐身版”替换掉系统的 Popen
    subprocess.Popen = NoWindowPopen
# ========================================================

# ... (下面的 class OcrApp 类定义保持不变) ...
# ================= 核心模块导入区域 =================
try:
    from core.rapidocr import RapidOcrConverter as OcrConverter
    OCR_ENGINE_NAME = "RapidOCR (极速)"
except ImportError:
    try:
        from core.ocr_pdf_html import OcrConverter
        OCR_ENGINE_NAME = "PaddleOCR (精准)"
    except ImportError:
        OCR_ENGINE_NAME = "未安装"

try:
    from core.word_pdf_html import DocToHtmlConverter
except ImportError:
    DocToHtmlConverter = None

try:
    from core.pdf_md import PdfMdConverter
except ImportError as e:
    PdfMdConverter = None

# ===================================================

# --- 新增类：用于重定向控制台输出 ---
class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        # 线程安全地更新界面
        self.widget.after(0, self._append_text, str)

    def _append_text(self, str):
        self.widget.config(state='normal')
        self.widget.insert(tk.END, str, (self.tag,))
        self.widget.see(tk.END)
        self.widget.config(state='disabled')

    def flush(self):
        pass

class OcrApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"智能文档审计系统 (全功能版)")
        self.root.geometry("850x780")
        
        # --- 路径配置 ---
        self.dev_poppler = r"D:\poppler-25.12.0\Library\bin"
        
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        self.dist_poppler = os.path.join(base_dir, "poppler", "Library", "bin")

        # --- 变量定义 ---
        self.file_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar() 
        self.mode_var = tk.StringVar(value="ocr") 
        
        self.init_ui()
        
        # === 核心修改：劫持所有 print 输出到界面 ===
        # 这样 core 文件夹里的报错（如 "RapidOCR 初始化失败"）就能看见了
        sys.stdout = TextRedirector(self.log_area, "stdout")
        sys.stderr = TextRedirector(self.log_area, "stderr")

    def init_ui(self):
        # 1. 功能选择
        frame_mode = tk.LabelFrame(self.root, text="第一步：选择功能模式", padx=10, pady=10)
        frame_mode.pack(fill="x", padx=10, pady=5)
        modes = [("📄 扫描件 OCR -> HTML", "ocr"), ("💻 数字 PDF -> HTML", "digital_pdf"),
                 ("📝 Word -> HTML", "word"), ("⬇️ PDF -> Markdown", "pdf2md"), ("⬆️ Markdown -> PDF", "md2pdf")]
        for i, (text, mode) in enumerate(modes):
            tk.Radiobutton(frame_mode, text=text, variable=self.mode_var, value=mode, 
                           command=self.update_file_filter).grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        # 2. 文件选择
        frame_file = tk.LabelFrame(self.root, text="第二步：选择文件", padx=10, pady=10)
        frame_file.pack(fill="x", padx=10, pady=5)
        tk.Entry(frame_file, textvariable=self.file_path_var, width=65).pack(side="left", padx=5)
        tk.Button(frame_file, text="📂 浏览文件", command=self.select_file).pack(side="left", padx=5)

        # 3. 输出位置
        frame_out = tk.LabelFrame(self.root, text="第三步：保存位置 (可选)", padx=10, pady=10)
        frame_out.pack(fill="x", padx=10, pady=5)
        tk.Entry(frame_out, textvariable=self.output_dir_var, width=65).pack(side="left", padx=5)
        tk.Button(frame_out, text="📂 选择文件夹", command=self.select_output_dir).pack(side="left", padx=5)

        # 4. 按钮
        frame_btn = tk.Frame(self.root, pady=5)
        frame_btn.pack(fill="x", padx=10)
        self.btn_run = tk.Button(frame_btn, text="🚀 开始处理", command=self.start_thread, 
                                 bg="#007bff", fg="white", font=("微软雅黑", 12, "bold"), height=2)
        self.btn_run.pack(fill="x")

        # 5. 日志
        frame_log = tk.LabelFrame(self.root, text="运行日志 (实时)", padx=10, pady=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(frame_log, height=12, state='disabled', font=("Consolas", 10))
        self.log_area.pack(fill="both", expand=True)

    def log(self, msg):
        print(msg) # 现在只需要 print，它会自动重定向到界面

    def update_file_filter(self): self.file_path_var.set("")
    
    def select_file(self):
        mode = self.mode_var.get()
        ft = [("Word", "*.docx")] if mode=="word" else [("Markdown", "*.md")] if mode=="md2pdf" else [("PDF", "*.pdf")]
        fn = filedialog.askopenfilename(filetypes=ft)
        if fn: self.file_path_var.set(fn)

    def select_output_dir(self):
        d = filedialog.askdirectory()
        if d: self.output_dir_var.set(d)

    def start_thread(self):
        if not self.file_path_var.get(): return messagebox.showwarning("提示", "请选择文件")
        self.btn_run.config(state="disabled", text="⏳ 处理中...", bg="#6c757d")
        self.log_area.config(state='normal'); self.log_area.delete(1.0, tk.END); self.log_area.config(state='disabled')
        threading.Thread(target=self.run_logic, args=(self.file_path_var.get(),), daemon=True).start()

    def run_logic(self, input_path):
        mode = self.mode_var.get()
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        out_dir = self.output_dir_var.get()
        if not out_dir: 
            out_dir = os.path.join(os.path.dirname(input_path), "output_result")
            if not os.path.exists(out_dir): os.makedirs(out_dir)

        try:
            success = False
            print(f"🔄 模式: {mode} | 文件: {base_name}")
            
            if mode == "ocr":
                poppler = self.dist_poppler if os.path.exists(self.dist_poppler) else self.dev_poppler
                if not os.path.exists(poppler):
                    print("❌ 致命错误: 未找到 Poppler 文件夹！")
                    return
                print(f"📂 Poppler路径: {poppler}")
                
                output_file = os.path.join(out_dir, f"{base_name}_ocr.html")
                converter = OcrConverter(poppler_path=poppler)
                success = converter.scanned_pdf_to_html(input_path, output_file)

            elif mode == "digital_pdf":
                output_file = os.path.join(out_dir, f"{base_name}_digital.html")
                success = DocToHtmlConverter().pdf_to_html(input_path, output_file)
            elif mode == "word":
                output_file = os.path.join(out_dir, f"{base_name}_word.html")
                success = DocToHtmlConverter().word_to_html(input_path, output_file)
            elif mode == "pdf2md":
                output_file = os.path.join(out_dir, f"{base_name}.md")
                success = PdfMdConverter().pdf_to_markdown(input_path, output_file)
            elif mode == "md2pdf":
                output_file = os.path.join(out_dir, f"{base_name}_restored.pdf")
                success = PdfMdConverter().markdown_to_pdf(input_path, output_file)

            if success:
                print(f"\n🎉 处理成功！文件已保存至: {output_file}")
                messagebox.showinfo("成功", "处理完成！")
            else:
                print("\n❌ 核心程序返回失败。请查看上方具体报错信息。")
                messagebox.showerror("失败", "处理失败，请查看日志")

        except Exception as e:
            print(f"❌ 发生异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal", text="🚀 开始处理", bg="#007bff"))

if __name__ == "__main__":
    root = tk.Tk()
    app = OcrApp(root)
    root.mainloop()