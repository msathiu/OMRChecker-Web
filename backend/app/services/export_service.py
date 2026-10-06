"""
Servicio de Exportación de Resultados OMR.
Genera reportes en JSON, CSV y Excel (.xlsx con openpyxl) con columnas dinámicas (q1..qN),
trazabilidad de fecha de carga, usuario y nombre del examen, y manejo explícito de errores.
"""
import csv
import io
import json
import re
from pathlib import Path
from typing import List, Optional

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.schemas.omr import BatchProcessResponse


class ExportService:
    @staticmethod
    def _extract_question_columns(batch: BatchProcessResponse) -> List[str]:
        """
        Extrae exactamente N preguntas (q1..qN) correspondientes a la cantidad real del examen.
        Si son 10 preguntas: q1..q10. Si son 20: q1..q20. Si son 30: q1..q30. Si son 40: q1..q40.
        Nunca agrega columnas vacías de preguntas que no pertenecen al examen.
        """
        if batch.question_count and batch.question_count > 0:
            return [f"q{i}" for i in range(1, batch.question_count + 1)]

        # Si no está especificado explícitamente en el batch, derivar de los audits
        detected_questions = []
        for r in batch.results:
            if r.audits:
                for a in r.audits:
                    if a.question not in detected_questions:
                        detected_questions.append(a.question)

        if detected_questions:
            def sort_key(q: str):
                match = re.search(r"\d+", q)
                return int(match.group()) if match else 999
            return sorted(detected_questions, key=sort_key)

        # Fallback a 40 preguntas estándar
        return [f"q{i}" for i in range(1, 41)]

    @staticmethod
    def to_omrchecker_csv_string(batch: BatchProcessResponse) -> str:
        """
        Genera el CSV estructurado:
        Fecha de carga, Usuario, Nombre del examen, file_id, score, q1..qN
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)

        question_cols = ExportService._extract_question_columns(batch)
        headers = ["Fecha de carga", "Usuario", "Nombre del examen", "file_id", "score"] + question_cols
        writer.writerow(headers)

        fecha_carga = batch.created_at or ""
        usuario = batch.user_name or batch.user_email or "Usuario"
        nombre_examen = batch.exam_name or "Examen OMR"

        for r in batch.results:
            score_val = "ERROR" if r.status == "ERROR" else r.score
            row = [
                fecha_carga,
                usuario,
                nombre_examen,
                r.original_name,
                score_val,
            ]
            for col in question_cols:
                if r.status == "ERROR":
                    row.append("")  # No inventar respuestas para hojas con error
                else:
                    row.append(r.responses.get(col, ""))
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def create_excel_workbook(batch: BatchProcessResponse) -> Workbook:
        """
        Crea el libro Excel (.xlsx) consistente con el CSV:
        1. Hoja 'Resultados': Fecha de carga, Usuario, Nombre del examen, file_id, score, q1..qN
        2. Hoja 'Detalle': Nombre del examen, Archivo, Pregunta, Marcada, Correcta, Resultado, Puntos
        """
        wb = Workbook()

        # Estilos visuales consistentes
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        cell_font = Font(name="Calibri", size=11)

        # -------------------------------------------------------------
        # Hoja 1: Resultados (Estructura idéntica al CSV)
        # -------------------------------------------------------------
        ws_res = wb.active
        ws_res.title = "Resultados"

        question_cols = ExportService._extract_question_columns(batch)
        headers_res = ["Fecha de carga", "Usuario", "Nombre del examen", "file_id", "score"] + question_cols

        ws_res.append(headers_res)

        for cell in ws_res[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        fecha_carga = batch.created_at or ""
        usuario = batch.user_name or batch.user_email or "Usuario"
        nombre_examen = batch.exam_name or "Examen OMR"

        for r in batch.results:
            score_val = "ERROR" if r.status == "ERROR" else r.score
            row_data = [
                fecha_carga,
                usuario,
                nombre_examen,
                r.original_name,
                score_val,
            ]
            for col in question_cols:
                if r.status == "ERROR":
                    row_data.append("")  # No inventar respuestas para hojas con error
                else:
                    row_data.append(r.responses.get(col, ""))

            ws_res.append(row_data)

        for row in ws_res.iter_rows(min_row=2, max_row=ws_res.max_row, max_col=ws_res.max_column):
            for cell in row:
                cell.font = cell_font
                cell.border = thin_border
                if cell.column == 5:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws_res.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_res.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # -------------------------------------------------------------
        # Hoja 2: Detalle por Pregunta
        # -------------------------------------------------------------
        ws_det = wb.create_sheet(title="Detalle")
        headers_det = ["Nombre del examen", "Archivo", "Pregunta", "Marcada", "Correcta", "Resultado", "Puntos"]
        ws_det.append(headers_det)

        for cell in ws_det[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        for r in batch.results:
            if r.status == "ERROR":
                ws_det.append([
                    nombre_examen,
                    r.original_name,
                    "N/A",
                    "N/A",
                    "N/A",
                    "ERROR",
                    r.error_message or "Error en detección",
                ])
            else:
                for a in r.audits:
                    ws_det.append([
                        nombre_examen,
                        r.original_name,
                        a.question,
                        a.marked,
                        str(a.allowed_answers),
                        a.verdict,
                        a.delta,
                    ])

        for row in ws_det.iter_rows(min_row=2, max_row=ws_det.max_row, max_col=ws_det.max_column):
            for cell in row:
                cell.font = cell_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws_det.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_det.column_dimensions[col_letter].width = max(max_len + 3, 12)

        return wb

    @staticmethod
    def to_excel_bytes(batch: BatchProcessResponse) -> bytes:
        wb = ExportService.create_excel_workbook(batch)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    @staticmethod
    def save_batch_results(batch: BatchProcessResponse, results_dir: Path):
        """Guarda todos los reportes (JSON, CSV y Excel) en la carpeta indicada."""
        results_dir.mkdir(parents=True, exist_ok=True)

        # 1. results.json
        json_path = results_dir / "results.json"
        with json_path.open("w", encoding="utf-8") as f:
            f.write(batch.model_dump_json(indent=2))

        # 2. results.csv compatible y estructurado
        csv_path = results_dir / "results.csv"
        with csv_path.open("w", encoding="utf-8") as f:
            f.write(ExportService.to_omrchecker_csv_string(batch))

        # 3. results.xlsx con openpyxl (Resultados + Detalle)
        xlsx_path = results_dir / "results.xlsx"
        wb = ExportService.create_excel_workbook(batch)
        wb.save(str(xlsx_path))


export_service = ExportService()
