import base64
import os
from odoo import models


class ReportVendorHandover(models.AbstractModel):
    _name = "report.gm_product_service.vendor_service_handover_report"

    def _get_report_values(self, docids, data=None):
        records = self.env["gm.product_service"].browse(docids)

        # Dapatkan path file image
        module_path = os.path.dirname(__file__)
        image_path = os.path.join(
            module_path, "..", "static", "src", "img", "hires-galerimedika-logo.jpg"
        )

        # Encode ke base64
        with open(image_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode("utf-8")

        logo_url = f"data:image/jpeg;base64,{image_data}"

        def format_date_indonesia(date_obj):
            if not date_obj:
                return ""
            months = {
                1: "Januari",
                2: "Februari",
                3: "Maret",
                4: "April",
                5: "Mei",
                6: "Juni",
                7: "Juli",
                8: "Agustus",
                9: "September",
                10: "Oktober",
                11: "November",
                12: "Desember",
            }
            return f"{date_obj.day} {months[date_obj.month]} {date_obj.year}"

        doc_values = []
        for rec in records:
            doc_values.append(
                {
                    "record": rec,
                    "formatted_date": format_date_indonesia(rec.date_document),
                }
            )

        return {
            "doc_ids": docids,
            "doc_model": "gm.product_service",
            "docs": doc_values,
            "logo_url": logo_url,  # ← ini yang dipakai di template
        }
