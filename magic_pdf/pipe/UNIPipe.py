import json

from loguru import logger
from magic_pdf.rw.AbsReaderWriter import AbsReaderWriter
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
from magic_pdf.libs.commons import join_path
from magic_pdf.pipe.AbsPipe import AbsPipe
from magic_pdf.user_api import parse_union_pdf, parse_ocr_pdf


class UNIPipe(AbsPipe):

    def __init__(self, pdf_bytes: bytes, model_list: list, image_writer: AbsReaderWriter, is_debug: bool = False):
        super().__init__(pdf_bytes, model_list, image_writer, is_debug)

    def pipe_classify(self):
        self.pdf_type = UNIPipe.classify(self.pdf_bytes)

    def pipe_parse(self):
        if self.pdf_type == self.PIP_TXT:
            self.pdf_mid_data = parse_union_pdf(self.pdf_bytes, self.model_list, self.image_writer,
                                                is_debug=self.is_debug)
        elif self.pdf_type == self.PIP_OCR:
            self.pdf_mid_data = parse_ocr_pdf(self.pdf_bytes, self.model_list, self.image_writer,
                                              is_debug=self.is_debug)

    def pipe_mk_uni_format(self, img_parent_path: str):
        content_list = AbsPipe.mk_uni_format(self.get_compress_pdf_mid_data(), img_parent_path)
        return content_list

    def pipe_mk_markdown(self, img_parent_path: str):
        markdown_content = AbsPipe.mk_markdown(self.get_compress_pdf_mid_data(), img_parent_path)
        return markdown_content


if __name__ == '__main__':
    # 测试
    drw = DiskReaderWriter(r"D:/project/20231108code-clean")

    pdf_file_path = r"linshixuqiu\19983-00.pdf"
    model_file_path = r"linshixuqiu\19983-00.json"
    pdf_bytes = drw.read(pdf_file_path, AbsReaderWriter.MODE_BIN)
    model_json_txt = drw.read(model_file_path, AbsReaderWriter.MODE_TXT)
    model_list = json.loads(model_json_txt)
    write_path = r"D:\project\20231108code-clean\linshixuqiu\19983-00"
    img_bucket_path = "imgs"
    img_writer = DiskReaderWriter(join_path(write_path, img_bucket_path))

    pipe = UNIPipe(pdf_bytes, model_list, img_writer, img_bucket_path)
    pipe.pipe_classify()
    pipe.pipe_parse()
    md_content = pipe.pipe_mk_markdown()
    try:
        content_list = pipe.pipe_mk_uni_format()
    except Exception as e:
        logger.exception(e)

    md_writer = DiskReaderWriter(write_path)
    md_writer.write(md_content, "19983-00.md", AbsReaderWriter.MODE_TXT)
    md_writer.write(json.dumps(pipe.pdf_mid_data, ensure_ascii=False, indent=4), "19983-00.json",
                    AbsReaderWriter.MODE_TXT)
    md_writer.write(str(content_list), "19983-00.txt", AbsReaderWriter.MODE_TXT)
