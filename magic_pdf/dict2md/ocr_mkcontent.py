from loguru import logger

from magic_pdf.libs.commons import join_path
from magic_pdf.libs.language import detect_lang
from magic_pdf.libs.markdown_utils import ocr_escape_special_markdown_char
from magic_pdf.libs.ocr_content_type import ContentType, BlockType
import wordninja
import re


def split_long_words(text):
    segments = text.split(' ')
    for i in range(len(segments)):
        words = re.findall(r'\w+|[^\w\s]', segments[i], re.UNICODE)
        for j in range(len(words)):
            if len(words[j]) > 15:
                words[j] = ' '.join(wordninja.split(words[j]))
        segments[i] = ''.join(words)
    return ' '.join(segments)


def ocr_mk_mm_markdown_with_para(pdf_info_list: list, img_buket_path):
    markdown = []
    for page_info in pdf_info_list:
        paras_of_layout = page_info.get("para_blocks")
        page_markdown = ocr_mk_markdown_with_para_core_v2(paras_of_layout, "mm", img_buket_path)
        markdown.extend(page_markdown)
    return '\n\n'.join(markdown)


def ocr_mk_nlp_markdown_with_para(pdf_info_dict: list):
    markdown = []
    for page_info in pdf_info_dict:
        paras_of_layout = page_info.get("para_blocks")
        page_markdown = ocr_mk_markdown_with_para_core_v2(paras_of_layout, "nlp")
        markdown.extend(page_markdown)
    return '\n\n'.join(markdown)


def ocr_mk_mm_markdown_with_para_and_pagination(pdf_info_dict: list, img_buket_path):
    markdown_with_para_and_pagination = []
    page_no = 0
    for page_info in pdf_info_dict:
        paras_of_layout = page_info.get("para_blocks")
        if not paras_of_layout:
            continue
        page_markdown = ocr_mk_markdown_with_para_core_v2(paras_of_layout, "mm", img_buket_path)
        markdown_with_para_and_pagination.append({
            'page_no': page_no,
            'md_content': '\n\n'.join(page_markdown)
        })
        page_no += 1
    return markdown_with_para_and_pagination


def ocr_mk_markdown_with_para_core(paras_of_layout, mode, img_buket_path=""):
    page_markdown = []
    for paras in paras_of_layout:
        for para in paras:
            para_text = ''
            for line in para:
                for span in line['spans']:
                    span_type = span.get('type')
                    content = ''
                    language = ''
                    if span_type == ContentType.Text:
                        content = span['content']
                        language = detect_lang(content)
                        if language == 'en':  # 只对英文长词进行分词处理，中文分词会丢失文本
                            content = ocr_escape_special_markdown_char(split_long_words(content))
                        else:
                            content = ocr_escape_special_markdown_char(content)
                    elif span_type == ContentType.InlineEquation:
                        content = f"${span['content']}$"
                    elif span_type == ContentType.InterlineEquation:
                        content = f"\n$$\n{span['content']}\n$$\n"
                    elif span_type in [ContentType.Image, ContentType.Table]:
                        if mode == 'mm':
                            content = f"\n![]({join_path(img_buket_path, span['image_path'])})\n"
                        elif mode == 'nlp':
                            pass
                    if content != '':
                        if language == 'en':  # 英文语境下 content间需要空格分隔
                            para_text += content + ' '
                        else:  # 中文语境下，content间不需要空格分隔
                            para_text += content
            if para_text.strip() == '':
                continue
            else:
                page_markdown.append(para_text.strip() + '  ')
    return page_markdown


def ocr_mk_markdown_with_para_core_v2(paras_of_layout, mode, img_buket_path=""):
    page_markdown = []
    for para_block in paras_of_layout:
        para_text = ''
        para_type = para_block['type']
        if para_type == BlockType.Text:
            para_text = merge_para_with_text(para_block)
        elif para_type == BlockType.Title:
            para_text = f"# {merge_para_with_text(para_block)}"
        elif para_type == BlockType.InterlineEquation:
            para_text = merge_para_with_text(para_block)
        elif para_type == BlockType.Image:
            if mode == 'nlp':
                continue
            elif mode == 'mm':
                for block in para_block['blocks']:
                    if block['type'] == BlockType.ImageBody:
                        for line in block['lines']:
                            for span in line['spans']:
                                if span['type'] == ContentType.Image:
                                    para_text = f"\n![]({join_path(img_buket_path, span['image_path'])})\n"
                for block in para_block['blocks']:
                    if block['type'] == BlockType.ImageCaption:
                        para_text += merge_para_with_text(block)
        elif para_type == BlockType.Table:
            if mode == 'nlp':
                continue
            elif mode == 'mm':
                for block in para_block['blocks']:
                    if block['type'] == BlockType.TableBody:
                        for line in block['lines']:
                            for span in line['spans']:
                                if span['type'] == ContentType.Table:
                                    para_text = f"\n![]({join_path(img_buket_path, span['image_path'])})\n"
                for block in para_block['blocks']:
                    if block['type'] == BlockType.TableCaption:
                        para_text += merge_para_with_text(block)
                    elif block['type'] == BlockType.TableFootnote:
                        para_text += merge_para_with_text(block)

        if para_text.strip() == '':
            continue
        else:
            page_markdown.append(para_text.strip() + '  ')

    return page_markdown


def merge_para_with_text(para_block):
    para_text = ''
    for line in para_block['lines']:
        for span in line['spans']:
            span_type = span['type']
            content = ''
            language = ''
            if span_type == ContentType.Text:
                content = span['content']
                language = detect_lang(content)
                if language == 'en':  # 只对英文长词进行分词处理，中文分词会丢失文本
                    content = ocr_escape_special_markdown_char(split_long_words(content))
                else:
                    content = ocr_escape_special_markdown_char(content)
            elif span_type == ContentType.InlineEquation:
                content = f"${span['content']}$"
            elif span_type == ContentType.InterlineEquation:
                content = f"\n$$\n{span['content']}\n$$\n"

            if content != '':
                if language == 'en':  # 英文语境下 content间需要空格分隔
                    para_text += content + ' '
                else:  # 中文语境下，content间不需要空格分隔
                    para_text += content
    return para_text


def para_to_standard_format(para, img_buket_path):
    para_content = {}
    if len(para) == 1:
        para_content = line_to_standard_format(para[0], img_buket_path)
    elif len(para) > 1:
        para_text = ''
        inline_equation_num = 0
        for line in para:
            for span in line['spans']:
                language = ''
                span_type = span.get('type')
                content = ""
                if span_type == ContentType.Text:
                    content = span['content']
                    language = detect_lang(content)
                    if language == 'en':  # 只对英文长词进行分词处理，中文分词会丢失文本
                        content = ocr_escape_special_markdown_char(split_long_words(content))
                    else:
                        content = ocr_escape_special_markdown_char(content)
                elif span_type == ContentType.InlineEquation:
                    content = f"${span['content']}$"
                    inline_equation_num += 1

                if language == 'en':  # 英文语境下 content间需要空格分隔
                    para_text += content + ' '
                else:  # 中文语境下，content间不需要空格分隔
                    para_text += content
        para_content = {
            'type': 'text',
            'text': para_text,
            'inline_equation_num': inline_equation_num
        }
    return para_content


def para_to_standard_format_v2(para_block, img_buket_path):
    para_type = para_block['type']
    if para_type == BlockType.Text:
        para_content = {
            'type': 'text',
            'text': merge_para_with_text(para_block),
        }
    elif para_type == BlockType.Title:
        para_content = {
            'type': 'text',
            'text': merge_para_with_text(para_block),
            'text_level': 1
        }
    elif para_type == BlockType.InterlineEquation:
        para_content = {
            'type': 'equation',
            'text': merge_para_with_text(para_block),
            'text_format': "latex"
        }
    elif para_type == BlockType.Image:
        para_content = {
            'type': 'image',
        }
        for block in para_block['blocks']:
            if block['type'] == BlockType.ImageBody:
                para_content['img_path'] = join_path(img_buket_path, block["lines"][0]["spans"][0]['image_path'])
            if block['type'] == BlockType.ImageCaption:
                para_content['img_caption'] = merge_para_with_text(block)
    elif para_type == BlockType.Table:
        para_content = {
            'type': 'table',
        }
        for block in para_block['blocks']:
            if block['type'] == BlockType.TableBody:
                para_content['img_path'] = join_path(img_buket_path, block["lines"][0]["spans"][0]['image_path'])
            if block['type'] == BlockType.TableCaption:
                para_content['table_caption'] = merge_para_with_text(block)
            if block['type'] == BlockType.TableFootnote:
                para_content['table_footnote'] = merge_para_with_text(block)

    return para_content


def make_standard_format_with_para(pdf_info_dict: list, img_buket_path: str):
    content_list = []
    for page_info in pdf_info_dict:
        paras_of_layout = page_info.get("para_blocks")
        if not paras_of_layout:
            continue
        for para_block in paras_of_layout:
            para_content = para_to_standard_format_v2(para_block, img_buket_path)
            content_list.append(para_content)
    return content_list


def line_to_standard_format(line, img_buket_path):
    line_text = ""
    inline_equation_num = 0
    for span in line['spans']:
        if not span.get('content'):
            if not span.get('image_path'):
                continue
            else:
                if span['type'] == ContentType.Image:
                    content = {
                        'type': 'image',
                        'img_path': join_path(img_buket_path, span['image_path'])
                    }
                    return content
                elif span['type'] == ContentType.Table:
                    content = {
                        'type': 'table',
                        'img_path': join_path(img_buket_path, span['image_path'])
                    }
                    return content
        else:
            if span['type'] == ContentType.InterlineEquation:
                interline_equation = span['content']
                content = {
                    'type': 'equation',
                    'latex': f"$$\n{interline_equation}\n$$"
                }
                return content
            elif span['type'] == ContentType.InlineEquation:
                inline_equation = span['content']
                line_text += f"${inline_equation}$"
                inline_equation_num += 1
            elif span['type'] == ContentType.Text:
                text_content = ocr_escape_special_markdown_char(span['content'])  # 转义特殊符号
                line_text += text_content
    content = {
        'type': 'text',
        'text': line_text,
        'inline_equation_num': inline_equation_num
    }
    return content


def ocr_mk_mm_standard_format(pdf_info_dict: list):
    """
    content_list
    type         string      image/text/table/equation(行间的单独拿出来，行内的和text合并)
    latex        string      latex文本字段。
    text         string      纯文本格式的文本数据。
    md           string      markdown格式的文本数据。
    img_path     string      s3://full/path/to/img.jpg
    """
    content_list = []
    for page_info in pdf_info_dict:
        blocks = page_info.get("preproc_blocks")
        if not blocks:
            continue
        for block in blocks:
            for line in block['lines']:
                content = line_to_standard_format(line)
                content_list.append(content)
    return content_list
