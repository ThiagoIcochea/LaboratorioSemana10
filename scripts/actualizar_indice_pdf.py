#!/usr/bin/env python3
"""
Actualiza el índice (campo TOC) del informe con LibreOffice sin interfaz (UNO) y exporta el PDF.
Uso: python3 scripts/actualizar_indice_pdf.py
"""
import os
import pathlib
import subprocess
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCX = ROOT / "informe/Informe_Laboratorio_Monitoreo_Cloud.docx"


def prop(n, v):
    p = PropertyValue()
    p.Name, p.Value = n, v
    return p


prof = tempfile.mkdtemp()
proc = subprocess.Popen(["soffice", f"-env:UserInstallation=file://{prof}", "--headless", "--norestore",
                         "--accept=socket,host=127.0.0.1,port=2002;urp;"],
                        env=dict(os.environ, HOME=prof))
try:
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(60):
        try:
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(1)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    url = uno.systemPathToFileUrl(str(DOCX))
    doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
    idx = doc.getDocumentIndexes()
    total = idx.getCount()
    for i in range(total):
        idx.getByIndex(i).update()
    doc.refresh()
    doc.storeToURL(url, (prop("FilterName", "MS Word 2007 XML"),))
    doc.storeToURL(uno.systemPathToFileUrl(str(DOCX.with_suffix(".pdf"))), (prop("FilterName", "writer_pdf_Export"),))
    doc.close(True)
    print(f"Índice actualizado ({total} índice/s) y PDF exportado")
finally:
    try:
        desktop.terminate()
    except Exception:
        pass
    proc.terminate()
