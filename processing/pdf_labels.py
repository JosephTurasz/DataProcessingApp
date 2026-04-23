from __future__ import annotations

import os
import tempfile

import fitz

from config.constants import PDF_LABEL_WIDTH_PT,PDF_LABEL_HEIGHT_PT,PDF_LABEL_FONT,PDF_LABEL_FONT_SIZE,PDF_LABEL_ROTATE

def append_label(input_pdf: str, enabled: bool) -> str:
    if not enabled:
        return input_pdf

    base = os.path.splitext(os.path.basename(input_pdf))[0]
    label_text = base.split("-", 1)[0]

    src = fitz.open(input_pdf)
    fd, temp_out = tempfile.mkstemp(suffix="_withlabel.pdf")
    os.close(fd)

    out = fitz.open()
    out.insert_pdf(src)

    page = out.new_page(width=PDF_LABEL_WIDTH_PT, height=PDF_LABEL_HEIGHT_PT)
    rect = fitz.Rect(0, 0, PDF_LABEL_WIDTH_PT, PDF_LABEL_HEIGHT_PT)

    page.insert_textbox(rect,label_text,fontsize=PDF_LABEL_FONT_SIZE,fontname=PDF_LABEL_FONT,color=(0, 0, 0),align=fitz.TEXT_ALIGN_CENTER,rotate=PDF_LABEL_ROTATE,)

    out.save(temp_out)
    out.close()
    src.close()

    return temp_out