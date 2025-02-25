"""
这里实现2个click命令：
第一个：
 接收一个完整的s3路径，例如：s3://llm-pdf-text/pdf_ebook_and_paper/pre-clean-mm-markdown/v014/part-660420b490be-000008.jsonl?bytes=0,81350
    1）根据~/magic-pdf.json里的ak,sk等，构造s3cliReader读取到这个jsonl的对应行，返回json对象。
    2）根据Json对象里的pdf的s3路径获取到他的ak,sk,endpoint，构造出s3cliReader用来读取pdf
    3）从magic-pdf.json里读取到本地保存图片、Md等的临时目录位置,构造出LocalImageWriter，用来保存截图
    4）从magic-pdf.json里读取到本地保存图片、Md等的临时目录位置,构造出LocalIRdWriter，用来读写本地文件
    
    最后把以上步骤准备好的对象传入真正的解析API
    
第二个：
  接收1）pdf的本地路径。2）模型json文件（可选）。然后：
    1）根据~/magic-pdf.json读取到本地保存图片、md等临时目录的位置，构造出LocalImageWriter，用来保存截图
    2）从magic-pdf.json里读取到本地保存图片、Md等的临时目录位置,构造出LocalIRdWriter，用来读写本地文件
    3）根据约定，根据pdf本地路径，推导出pdf模型的json，并读入
    

效果：
python magicpdf.py --json  s3://llm-pdf-text/scihub/xxxx.json?bytes=0,81350 
python magicpdf.py --pdf  /home/llm/Downloads/xxxx.pdf --model /home/llm/Downloads/xxxx.json  或者 python magicpdf.py --pdf  /home/llm/Downloads/xxxx.pdf
"""

import os
import json as json_parse
import sys
import click
from loguru import logger
from pathlib import Path

from magic_pdf.libs.draw_bbox import draw_layout_bbox, draw_span_bbox
from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.pipe.OCRPipe import OCRPipe
from magic_pdf.pipe.TXTPipe import TXTPipe
from magic_pdf.libs.config_reader import get_s3_config
from magic_pdf.libs.path_utils import (
    parse_s3path,
    parse_s3_range_params,
    remove_non_official_s3_args,
)
from magic_pdf.libs.config_reader import get_local_dir
from magic_pdf.rw.S3ReaderWriter import S3ReaderWriter
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
from magic_pdf.rw.AbsReaderWriter import AbsReaderWriter

parse_pdf_methods = click.Choice(["ocr", "txt", "auto"])


def prepare_env(pdf_file_name, method):
    local_parent_dir = os.path.join(
        get_local_dir(), "magic-pdf", pdf_file_name, method
    )

    local_image_dir = os.path.join(local_parent_dir, "images")
    local_md_dir = local_parent_dir
    os.makedirs(local_image_dir, exist_ok=True)
    os.makedirs(local_md_dir, exist_ok=True)
    return local_image_dir, local_md_dir


def _do_parse(pdf_file_name, pdf_bytes, model_list, parse_method, image_writer, md_writer, image_dir, local_md_dir):
    if parse_method == "auto":
        pipe = UNIPipe(pdf_bytes, model_list, image_writer, is_debug=True)
    elif parse_method == "txt":
        pipe = TXTPipe(pdf_bytes, model_list, image_writer, is_debug=True)
    elif parse_method == "ocr":
        pipe = OCRPipe(pdf_bytes, model_list, image_writer, is_debug=True)
    else:
        print("unknow parse method")
        os.exit(1)

    pipe.pipe_classify()
    pipe.pipe_parse()
    pdf_info = pipe.pdf_mid_data['pdf_info']
    draw_layout_bbox(pdf_info, pdf_bytes, local_md_dir)
    draw_span_bbox(pdf_info, pdf_bytes, local_md_dir)
    md_content = pipe.pipe_mk_markdown(image_dir)
    #part_file_name = datetime.now().strftime("%H-%M-%S")
    md_writer.write(
        content=md_content, path=f"{pdf_file_name}.md", mode=AbsReaderWriter.MODE_TXT
    )
    md_writer.write(
        content=json_parse.dumps(pipe.pdf_mid_data, ensure_ascii=False, indent=4),
        path=f"{pdf_file_name}.json",
        mode=AbsReaderWriter.MODE_TXT,
    )
    try:
        content_list = pipe.pipe_mk_uni_format(image_dir)
    except Exception as e:
        logger.exception(e)
    md_writer.write(
        str(content_list), f"{pdf_file_name}.txt", AbsReaderWriter.MODE_TXT
    )


@click.group()
def cli():
    pass


@cli.command()
@click.option("--json", type=str, help="输入一个S3路径")
@click.option(
    "--method",
    type=parse_pdf_methods,
    help="指定解析方法。txt: 文本型 pdf 解析方法， ocr: 光学识别解析 pdf, auto: 程序智能选择解析方法",
    default="auto",
)
def json_command(json, method):
    if not json.startswith("s3://"):
        print("usage: python magipdf.py --json s3://some_bucket/some_path")
        os.exit(1)

    def read_s3_path(s3path):
        bucket, key = parse_s3path(s3path)

        s3_ak, s3_sk, s3_endpoint = get_s3_config(bucket)
        s3_rw = S3ReaderWriter(
            s3_ak, s3_sk, s3_endpoint, "auto", remove_non_official_s3_args(s3path)
        )
        may_range_params = parse_s3_range_params(s3path)
        if may_range_params is None or 2 != len(may_range_params):
            byte_start, byte_end = 0, None
        else:
            byte_start, byte_end = int(may_range_params[0]), int(may_range_params[1])
            byte_end += byte_start - 1
        return s3_rw.read_jsonl(
            remove_non_official_s3_args(s3path),
            byte_start,
            byte_end,
            AbsReaderWriter.MODE_BIN,
        )

    jso = json_parse.loads(read_s3_path(json).decode("utf-8"))
    s3_file_path = jso["file_location"]
    pdf_file_name = Path(s3_file_path).stem
    pdf_data = read_s3_path(s3_file_path)
    local_image_dir, local_md_dir = prepare_env(pdf_file_name, method)
    
    local_image_rw, local_md_rw = DiskReaderWriter(local_image_dir), DiskReaderWriter(
        local_md_dir
    )

    _do_parse(
        pdf_file_name,
        pdf_data,
        jso["doc_layout_result"],
        method,
        local_image_rw,
        local_md_rw,
        os.path.basename(local_image_dir),
        local_md_dir
    )


@cli.command()
@click.option(
    "--pdf", type=click.Path(exists=True), required=True, help="PDF文件的路径"
)
@click.option("--model", type=click.Path(exists=True), help="模型的路径")
@click.option(
    "--method",
    type=parse_pdf_methods,
    help="指定解析方法。txt: 文本型 pdf 解析方法， ocr: 光学识别解析 pdf, auto: 程序智能选择解析方法",
    default="auto",
)
def pdf_command(pdf, model, method):
    # 这里处理pdf和模型相关的逻辑
    if model is None:
        model = pdf.replace(".pdf", ".json")
        if not os.path.exists(model):
            print(f"make sure json {model} existed and place under {os.path.dirname(pdf)}", file=sys.stderr)
            exit(1)

    def read_fn(path):
        disk_rw = DiskReaderWriter(os.path.dirname(path))
        return disk_rw.read(os.path.basename(path), AbsReaderWriter.MODE_BIN)

    pdf_data = read_fn(pdf)
    jso = json_parse.loads(read_fn(model).decode("utf-8"))
    pdf_file_name = Path(pdf).stem
    local_image_dir, local_md_dir = prepare_env(pdf_file_name, method)
    local_image_rw, local_md_rw = DiskReaderWriter(local_image_dir), DiskReaderWriter(
        local_md_dir
    )
    _do_parse(
        pdf_file_name,
        pdf_data,
        jso,
        method,
        local_image_rw,
        local_md_rw,
        os.path.basename(local_image_dir),
        local_md_dir
    )


if __name__ == "__main__":
    """
    python magic_pdf/cli/magicpdf.py json-command --json s3://llm-pdf-text/pdf_ebook_and_paper/manual/v001/part-660407a28beb-000002.jsonl?bytes=0,63551
    """
    cli()
