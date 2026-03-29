from app.docs import normalize_pdf_text_as_markdown


def test_normalize_pdf_promotes_numbered_headings_and_drops_toc():
    source = """NVM Express Base Specification, Revision 2.1

    1 INTRODUCTION .............................................................................................
    1.1 Overview ...............................................................................................
    2 THEORY OF OPERATION ......................................................................................
    5.2 Memory-Based Transport Admin Commands (PCIe) ..........................................................

    1 INTRODUCTION
    Overview paragraph.
    1.1 Overview
Detailed paragraph.
5.2 Memory-Based Transport Admin Commands (PCIe)
Command paragraph.
"""
    output = normalize_pdf_text_as_markdown(source, "NVMe Spec")
    assert "# NVMe Spec" in output
    assert "................................................................" not in output
    assert "# 1 INTRODUCTION" in output
    assert "## 1.1 Overview" in output
    assert "## 5.2 Memory-Based Transport Admin Commands (PCIe)" in output
