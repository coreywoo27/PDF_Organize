# PDF_Organize

用于快速复习的试卷 PDF 知识点统计工具,适合考前临时抱佛脚，想拿高分的学生。

我构建了一个用于快速复习的多文档 PDF 知识点统计工具。它能够读取多个 PDF 文件，自动按题目切分内容，逐题提取涉及的知识点、核心公式、符号含义和解题作用，并对所有文档中的知识点进行标准化合并与频率统计。最终，程序会生成一份 Markdown 复习报告，将高频知识点按出现次数排序，并保留每个知识点对应的文档、题号和页码，帮助我快速定位重点内容，优先复习最常出现、最值得掌握的考点。

## 新增桌面 App

现在项目新增了一个轻量桌面 app，可以从指定文件夹中扫描 PDF，并由用户选择要分析的 PDF 文件。

## 安装依赖

```bash
git clone https://github.com/coreywoo27/PDF_Organize.git
cd PDF_Organize
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 启动 App

```bash
python3 -m pdf_review_app
```

## 使用流程

1. 选择包含往年试卷 PDF 的文件夹，例如仓库内置的 `mat1002papers/`，或你自己的 PDF 文件夹。
2. 在列表中选择要分析的 PDF 文件。
3. 选择报告输出文件夹。
4. 点击 `Analyze Selected PDFs`。

App 会生成：

- `pdf_quick_review_report.md`
- `pdf_question_analysis.json`

原来的命令行脚本仍然可用：

```bash
python3 -m mat1002_pdf_review exam1.pdf exam2.pdf --output report.md --json-output analysis.json
```

如果不传入 PDF 参数，命令行脚本会默认读取仓库内 `mat1002papers/` 目录中的五份 MAT1002 试卷。报告默认输出到运行命令时所在的当前目录，而不是某个固定的个人电脑路径。

```bash
python3 -m mat1002_pdf_review --output report.md --json-output analysis.json
```
