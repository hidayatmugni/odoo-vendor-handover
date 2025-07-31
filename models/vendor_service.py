from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io
import os
import xlsxwriter


class VendorServiceHandover(models.Model):
    _name = "gm.product_service"
    _description = "Vendor Service Handover"
    _order = "name desc"

    name = fields.Char(
        string="Handover ID",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: self._generate_handover_id(),
    )

    vendor_id = fields.Many2one(
        "res.partner",
        string="Nama Vendor",
        domain="[('supplier_rank', '>', 0)]",
        required=True,
    )
    invoice_number = fields.Char(string="Nomor Invoice Pembelian")
    # alamat galeri medika
    address = fields.Char(string="Alamat")
    postcode = fields.Char("Kode POS")
    city = fields.Char(string="Kota")
    telpon = fields.Char(string="No Hp")

    date_document = fields.Date(
        string="Tanggal Dokumen", default=fields.Date.context_today, store=True
    )
    outlet_id = fields.Many2one("stock.warehouse", string="Lokasi", required=True)

    state = fields.Selection(
        [
            ("open", "Open - Belum Diserahkan ke Vendor"),
            ("in_progress", "In Progress - Sudah Diserahkan ke Vendor"),
            ("close", "Close - Sudah Menerima Pengembalian Produk Dari Vendor"),
        ],
        string="Status",
        default="open",
    )
    note = fields.Text(string="Note", size=500)

    line_ids = fields.One2many(
        "gm.vendor_service_line", "handover_id", string="Produk Servis"
    )
    to_vendor_id = fields.One2many(
        "gm.vendor_service_to_vendor", "handover_id", string="Data Serah Terima ke Vendor"
    )
    from_vendor_id = fields.One2many(
        "gm.vendor_service_from_vendor",
        "handover_id",
        string="Data Pengembalian dari Vendor",
    )

    first_product = fields.Char(compute="_compute_first_product", string="Nama Produk", store=True)
    first_qty = fields.Integer(compute="_compute_first_qty", string="Qty")

    def _generate_handover_id(self):
        sequence = (
            self.env["ir.sequence"].next_by_code("gm.product_service") or "00001"
        )
        while f"ID-S{sequence.zfill(5)}" in self.search([("name", "!=", False)]).mapped(
            "name"
        ):
            sequence = str(int(sequence) + 1).zfill(5)
        return f"ID-S{sequence.zfill(5)}"

    @api.depends("line_ids")
    def _compute_first_product(self):
        for record in self:
            record.first_product = (
                record.line_ids[:1].mapped("product_id.display_name")[0]
                if record.line_ids
                else ""
            )

    @api.depends("line_ids")
    def _compute_first_qty(self):
        for record in self:
            record.first_qty = (
                record.line_ids[:1].mapped("qty")[0] if record.line_ids else 0
            )

    def _check_attachment_size(
        self,
        attachments,
        max_image_size=10 * 1024 * 1024,
        max_video_size=200 * 1024 * 1024,
    ):
        for attachment in attachments:
            size = len(base64.b64decode(attachment.datas)) if attachment.datas else 0
            if (
                attachment.mimetype
                and "image" in attachment.mimetype
                and size > max_image_size
            ):
                raise ValidationError(_("Ukuran gambar melebihi 10MB!"))
            elif (
                attachment.mimetype
                and "video" in attachment.mimetype
                and size > max_video_size
            ):
                raise ValidationError(_("Ukuran video melebihi 200MB!"))

    @api.onchange("line_ids")
    def _onchange_line_ids(self):
        for line in self.line_ids:
            self._check_attachment_size(line.attachment_ids)

    @api.onchange("to_vendor_id")
    def _onchange_to_vendor_id(self):
        for item in self.to_vendor_id:
            self._check_attachment_size(item.handover_doc)

    @api.onchange("from_vendor_id")
    def _onchange_from_vendor_id(self):
        for item in self.from_vendor_id:
            self._check_attachment_size(item.return_doc)

    def export_excel(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Vendor Service Report")

        # Fit ke A4
        worksheet.set_paper(9)
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(top=0.3, bottom=0.5, left=0.4, right=0.4)

        # Format
        bold = workbook.add_format({"bold": True, "font_size": 9,})
        title = workbook.add_format({"bold": True, "font_size": 14, "align": "center"})
        wrap_text = workbook.add_format({"font_size": 9, "text_wrap": True, "valign": "top", "align": "left"})
        bordered_center = workbook.add_format({"font_size": 9, "border": 1, "align": "center", "valign": "top"})
        header_format = workbook.add_format({"font_size": 9, "bold": True, "align": "center", "bg_color": "#D3D3D3", "border": 1})
        wrap_note = workbook.add_format({"font_size": 9, "text_wrap": True, "valign": "top", "border": 1})
        worksheet.set_default_row(15)  # default tinggi baris lebih kecil


        row = 0

        # Judul
        worksheet.merge_range(row, 0, row, 3, "Vendor Service Handover", title)
        row += 2
        partner = self.outlet_id.partner_id
        # Informasi Outlet & Vendor
        worksheet.write(row, 0, "Outlet:", bold)
        worksheet.write(row, 1, self.outlet_id.name or '', wrap_text)
        worksheet.write(row, 2, "Kepada Yth.:", bold)
        worksheet.write(row, 3, self.vendor_id.name or '', wrap_text)
        row += 1

        worksheet.write(row, 0, "Alamat:", bold)
        worksheet.write(row, 1, partner.street or '', wrap_text)
        worksheet.write(row, 2, "Alamat:", bold)
        worksheet.write(row, 3, self.vendor_id.street or '', wrap_text)
        row += 1

        worksheet.write(row, 0, "Kota - Kode Pos:", bold)
        worksheet.write(row, 1, f"{partner.city or ''} - {partner.zip or ''}", wrap_text)
        worksheet.write(row, 2, "Kota - Kode Pos:", bold)
        vendor_city = f"{self.vendor_id.city or ''} - {self.vendor_id.zip or ''}"
        worksheet.write(row, 3, vendor_city, wrap_text)
        row += 1

        worksheet.write(row, 0, "Telp:", bold)
        worksheet.write(row, 1, partner.mobile or '', wrap_text)
        worksheet.write(row, 2, "Telp Vendor:", bold)
        vendor_phone = " / ".join(filter(None, [self.vendor_id.mobile, self.vendor_id.phone]))
        worksheet.write(row, 3, vendor_phone, wrap_text)
        row += 2

        # Informasi Dokumen (gabung label + value jadi satu kolom)
        worksheet.merge_range(row, 0, row, 1, f"ID Document : {self.name or ''}", wrap_text)
        worksheet.merge_range(row, 2, row, 3, f"Tanggal Dokumen : {fields.Date.to_string(self.date_document) or ''}", wrap_text)
        row += 1

        worksheet.merge_range(row, 0, row, 1, f"Vendor : {self.vendor_id.name or ''}", wrap_text)
        worksheet.merge_range(row, 2, row, 3, f"Lokasi : {self.outlet_id.name or ''}", wrap_text)
        row += 1

        worksheet.merge_range(row, 0, row, 1, f"No Invoice : {self.invoice_number or ''}", wrap_text)
        worksheet.merge_range(row, 2, row, 3, f"Status : {dict(self._fields['state'].selection).get(self.state, '') or ''}", wrap_text)
        row += 2

        # Tabel Produk
        worksheet.write(row, 0, "Detail Produk Servis", bold)
        row += 1
        worksheet.write_row(row, 0, ["Nama Produk", "Qty", "Deskripsi", "Attachment"], header_format)
        row += 1

        for line in self.line_ids:
            worksheet.write(row, 0, line.product_id.display_name or "", wrap_note)
            worksheet.write(row, 1, line.qty or 0, bordered_center)
            worksheet.write(row, 2, (line.description or "").replace('\r\n', '\n'), wrap_note)
            if line.attachment_ids:
                image = line.attachment_ids.filtered(lambda a: "image" in a.mimetype)
                if image:
                    worksheet.write(row, 3, image[0].name or '', wrap_note)
            else:
                worksheet.write(row, 3, "", wrap_note)
            row += 1

        # Note
        row += 1
        worksheet.write(row, 0, "Catatan", bold)
        row += 1
        worksheet.merge_range(row, 0, row + 3, 3, self.note or "", wrap_note)
        row += 3

        # Serah Terima ke Vendor
        row += 2
        worksheet.write(row, 0, "Serah Terima ke Vendor", bold)
        row += 1
        worksheet.write_row(row, 0, ["Nama Penerima", "Tanggal", "Referensi Stock Move", "Attachment"], header_format)
        row += 1

        for item in self.to_vendor_id:
            worksheet.write(row, 0, item.recipient_name or "", bordered_center)
            worksheet.write(row, 1, fields.Date.to_string(item.date_sent) or "", bordered_center)
            worksheet.write(row, 2, item.stock_move_id.name or "", bordered_center)
            if item.handover_doc:
                image = item.handover_doc.filtered(lambda a: "image" in a.mimetype)
                if image:
                    worksheet.write(row, 3, image[0].name or "", wrap_note)
            else:
                worksheet.write(row, 3, "", wrap_note)
            row += 1

        # Pengembalian dari Vendor
        row += 2
        worksheet.write(row, 0, "Pengembalian dari Vendor", bold)
        row += 1
        worksheet.write_row(row, 0, ["Nama Penerima", "Tanggal", "Referensi Stock Move", "Attachment"], header_format)
        row += 1

        for item in self.from_vendor_id:
            worksheet.write(row, 0, item.recipient_name or "", bordered_center)
            worksheet.write(row, 1, fields.Date.to_string(item.date_received) or "", bordered_center)
            worksheet.write(row, 2, item.stock_move_id.name or "", bordered_center)
            if item.return_doc:
                image = item.return_doc.filtered(lambda a: "image" in a.mimetype)
                if image:
                    worksheet.write(row, 3, image[0].name or "", wrap_note)
            else:
                worksheet.write(row, 3, "", wrap_note)
            row += 1

        # Ukuran kolom
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 25)
        worksheet.set_column("C:C", 40)
        worksheet.set_column("D:D", 40)

        workbook.close()
        output.seek(0)

        attachment = self.env["ir.attachment"].create({
            "name": f"Vendor_Service_{self.name or 'handover'}.xlsx",
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    # fix editable pdf from excel
    def export_excel_editable(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Editable Vendor Report')

        # Setup A4 Fit Print
        worksheet.set_paper(9)
        worksheet.set_portrait()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(top=0.3, bottom=0.5, left=0.4, right=0.4)

        # Format
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})
        bold = workbook.add_format({'bold': True})
        normal = workbook.add_format({'font_size': 9})
        center = workbook.add_format({'font_size': 9, 'align': 'center'})
        title = workbook.add_format({'bold': True, 'font_size': 11, 'align': 'center'})
        header_format = workbook.add_format({'font_size': 9, 'bold': True, 'align': 'center', 'bg_color': '#D3D3D3', 'border': 1})
        wrap_text = workbook.add_format({'text_wrap': True, 'valign': 'top', 'align': 'left', 'font_size': 9})
        wrap_text_center = workbook.add_format({ 'text_wrap': True, 'valign': 'top', 'align': 'center', 'font_size': 9,'border': 1})
        wrap_text_border = workbook.add_format({'text_wrap': True, 'valign': 'top', 'align': 'left', 'font_size': 9, 'border': 1})
        wrap_text_catatan = workbook.add_format({'font_size': 9, 'text_wrap': True, 'valign': 'top', 'align': 'left', 'border': 1})


        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'img', 'hires-galerimedika-logo.jpg')
        worksheet.insert_image(2, 1, logo_path, {'x_scale': 0.1, 'y_scale': 0.1})

        row = 5

        # Outlet & Vendor Info
        worksheet.write(row, 1, self.outlet_id.name or '', wrap_text)
        worksheet.write(row, 3, self.vendor_id.name or '', wrap_text)
        row += 1
        partner = self.outlet_id.partner_id
        worksheet.write(row, 1, partner.street or '', wrap_text)
        vendor_address = self.vendor_id.street or ''
        worksheet.write(row, 3, vendor_address, wrap_text)
        row += 1
        
        outlet_city = f"{partner.city or ''} - {partner.zip or ''}"
        worksheet.write(row, 1, outlet_city, normal)
        vendor_city = f"{self.vendor_id.city or ''} - {self.vendor_id.zip or ''}"
        worksheet.write(row, 3, vendor_city, normal)
        row += 1

        worksheet.write(row, 1, f'Telp - {partner.mobile}' or '', normal)
        tel_vendor = " / ".join(filter(None, [self.vendor_id.mobile, self.vendor_id.phone]))
        worksheet.write(row, 3, f'Telp - {tel_vendor}', normal)

        # Tambahan Info Dokumen
        date_str = fields.Date.to_date(self.date_document).strftime("%d %B %Y")
        row += 2

        worksheet.write(row, 1, f"ID Document : {self.name or ''}", normal)
        worksheet.write(row, 3, f"Tanggal Dokumen : {date_str or ''}", normal)
        row += 1

        worksheet.write(row, 1, f"Vendor : {self.vendor_id.name or ''}", normal)
        worksheet.write(row, 3, f"Lokasi : {self.outlet_id.name or ''}", normal)
        row += 1

        worksheet.write(row, 1, f"Nomor Invoice : {self.invoice_number or ''}", normal)
        row += 2

        # Judul Tengah
        worksheet.merge_range(row, 1, row, 3, "Serah Terima Barang Galeri Medika", title)
        row += 2

        # Tabel Produk
        worksheet.write_row(row, 1, ["Nama Produk", "Qty", "Deskripsi"], header_format)
        row += 1
        for line in self.line_ids:
            worksheet.write(row, 1, line.product_id.display_name or '', wrap_text_border)
            worksheet.write(row, 2, line.qty or 0, wrap_text_center)
            worksheet.write(row, 3, line.description or '', wrap_text_border)
            row += 1

        # Note
        row += 1
        worksheet.write(row, 1, "Catatan", bold)
        row += 1
        worksheet.merge_range(row, 1, row, 3, self.note or '', wrap_text_catatan)
        row += 4

        # Tanda Tangan
        row += 2
        worksheet.write(row, 1, "Yang Menerima", bold_center)
        worksheet.write(row, 3, "Yang Menyerahkan", bold_center)
        row += 4
        worksheet.write(row, 1, "(........................)", center)
        worksheet.write(row, 3, "(.............................)", center)

        # Ukuran kolom
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 7)
        worksheet.set_column('D:D', 45)
        worksheet.set_column('E:E', 5)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': f"Editable_Vendor_Service_{self.name or 'handover'}.xlsx",
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

class VendorServiceLine(models.Model):
    _name = "gm.vendor_service_line"
    _description = "Vendor Service Line"

    handover_id = fields.Many2one("gm.product_service", string="Dokumen Servis")
    product_id = fields.Many2one("product.product", string="Produk", required=True)
    qty = fields.Integer(string="Qty", required=True)
    description = fields.Text(string="Deskripsi", size=500)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Foto/Video",
        domain="['|', ('mimetype', 'like', 'image/%'), ('mimetype', 'like', 'video/%')]",
    )


class VendorServiceToVendor(models.Model):
    _name = "gm.vendor_service_to_vendor"
    _description = "Data Serah Terima ke Vendor"

    handover_id = fields.Many2one("gm.product_service", string="Dokumen Servis")
    recipient_name = fields.Char(string="Nama Penerima (Vendor)", size=100)
    date_sent = fields.Date(string="Tanggal Serahkan ke Vendor")
    stock_move_id = fields.Many2one("stock.picking", string="Referensi Stock Move")
    handover_doc = fields.Many2many(
        "ir.attachment",
        string="Foto Dokumen Serah Terima",
        domain="[('mimetype', 'like', 'image/%')]",
    )

    @api.depends("handover_doc")
    def _compute_handover_doc_name(self):
        for record in self:
            record.handover_doc_name = (
                record.handover_doc.mapped("name")[0] if record.handover_doc else ""
            )


class VendorServiceFromVendor(models.Model):
    _name = "gm.vendor_service_from_vendor"
    _description = "Data Pengembalian dari Vendor"

    handover_id = fields.Many2one("gm.product_service", string="Dokumen Servis")
    recipient_name = fields.Char(string="Nama Penerima (Galeri Medika)", size=100)
    date_received = fields.Date(string="Tanggal Penerimaan")
    stock_move_id = fields.Many2one("stock.picking", string="Referensi Stock Move")
    return_doc = fields.Many2many(
        "ir.attachment",
        string="Foto Dokumen Penerimaan",
        domain="[('mimetype', 'like', 'image/%')]",
    )

    @api.depends("return_doc")
    def _compute_return_doc_name(self):
        for record in self:
            record.return_doc_name = (
                record.return_doc.mapped("name")[0] if record.return_doc else ""
            )
