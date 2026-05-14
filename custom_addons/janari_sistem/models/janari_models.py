import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class Satuan(models.Model):
    _name = 'janari.satuan'
    _description = 'Satuan Bahan Baku'

    name = fields.Char(string='Satuan', required=True)
    category = fields.Selection([
        ('berat', 'Berat'),
        ('volume', 'Volume'),
        ('jumlah', 'Jumlah'),
    ], string='Kategori', required=True, default='jumlah')
    factor = fields.Float(
        string='Faktor ke Satuan Terkecil', default=1.0,
        help='Contoh: Kilogram=1000 (1kg=1000g), Liter=1000 (1L=1000ml), Gram=1'
    )

# D-01 Tabel Bahan Baku
class BahanBaku(models.Model):
    _name = 'janari.bahan.baku'
    _description = 'Tabel Bahan Baku'

    name = fields.Char(string='Nama Bahan', required=True)
    jenis = fields.Char(string='Jenis')
    satuan = fields.Many2one('janari.satuan', string='Satuan')
    harga = fields.Float(string='Harga')
    vendor = fields.Char(string='Vendor')
    stok_saat_ini = fields.Float(string='Stok Saat Ini', default=0)
    reorder_point = fields.Float(string='Reorder Point', default=10)
    is_low_stock = fields.Boolean(string="Status Stok Rendah", compute="_compute_low_stock", store=True)

    def action_new_bahan_baku(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'janari.bahan.baku',
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('stok_saat_ini', 'reorder_point')
    def _compute_low_stock(self):
        for record in self:
            record.is_low_stock = record.stok_saat_ini <= record.reorder_point

# D-04 Tabel Menu
class Menu(models.Model):
    _name = 'janari.menu'
    _description = 'Tabel Menu'

    name = fields.Char(string='Nama Menu', required=True)
    harga_menu = fields.Float(string='Harga Menu', required=True)
    status_menu = fields.Selection([
        ('tersedia', 'Tersedia'),
        ('habis', 'Habis')
    ], string='Status Menu', default='tersedia')
    resep_ids = fields.One2many('janari.resep', 'menu_id', string='Komposisi Resep (BOM)')

# D-03 Tabel Resep (BOM)
class Resep(models.Model):
    _name = 'janari.resep'
    _description = 'Tabel Resep (Bill of Materials)'

    menu_id = fields.Many2one('janari.menu', string='Menu', required=True, ondelete='cascade')
    bahan_baku_id = fields.Many2one('janari.bahan.baku', string='Bahan Baku', required=True)
    jumlah_bahan = fields.Float(string='Jumlah Bahan', required=True)
    satuan = fields.Many2one('janari.satuan', string='Satuan', required=True)

    @api.onchange('bahan_baku_id')
    def _onchange_bahan_baku(self):
        if self.bahan_baku_id and self.bahan_baku_id.satuan:
            self.satuan = self.bahan_baku_id.satuan

# D-05 Tabel Pesanan
class Pesanan(models.Model):
    _name = 'janari.pesanan'
    _description = 'Tabel Pesanan'

    name = fields.Char(string='ID Pesanan', required=True, copy=False, readonly=True, default=lambda self: 'New')
    tanggal_pesanan = fields.Datetime(string='Tanggal Pesanan', default=fields.Datetime.now)
    status_pesanan = fields.Selection([
        ('draft', 'Menunggu Pembayaran'),
        ('confirmed', 'Terkonfirmasi'),
        ('done', 'Selesai')
    ], string='Status Keseluruhan', default='draft')
    total_harga = fields.Float(string='Total Harga', compute='_compute_total', store=True)
    detail_pesanan_ids = fields.One2many('janari.detail.pesanan', 'pesanan_id', string='Detail Item')

    @api.depends('detail_pesanan_ids.subtotal')
    def _compute_total(self):
        for record in self:
            record.total_harga = sum(item.subtotal for item in record.detail_pesanan_ids)

    def _convert_satuan(self, jumlah, dari_satuan, ke_satuan, nama_bahan):
        if not dari_satuan or not ke_satuan or dari_satuan == ke_satuan:
            return jumlah
        if dari_satuan.category != ke_satuan.category:
            raise UserError(
                f"Satuan tidak kompatibel untuk '{nama_bahan}': "
                f"{dari_satuan.name} ({dari_satuan.category}) "
                f"tidak bisa dikonversi ke {ke_satuan.name} ({ke_satuan.category})"
            )
        return jumlah * dari_satuan.factor / ke_satuan.factor

    def action_confirm(self):
        for record in self:
            if record.status_pesanan == 'draft':
                for item in record.detail_pesanan_ids:
                    for resep in item.menu_id.resep_ids:
                        kebutuhan_stok = self._convert_satuan(
                            resep.jumlah_bahan * item.jumlah,
                            resep.satuan,
                            resep.bahan_baku_id.satuan,
                            resep.bahan_baku_id.name,
                        )
                        if resep.bahan_baku_id.stok_saat_ini < kebutuhan_stok:
                            satuan_name = resep.bahan_baku_id.satuan.name or ''
                            raise UserError(
                                f"Stok '{resep.bahan_baku_id.name}' tidak cukup! "
                                f"Dibutuhkan: {kebutuhan_stok} {satuan_name}, "
                                f"Tersedia: {resep.bahan_baku_id.stok_saat_ini}"
                            )
                for item in record.detail_pesanan_ids:
                    for resep in item.menu_id.resep_ids:
                        kebutuhan_stok = self._convert_satuan(
                            resep.jumlah_bahan * item.jumlah,
                            resep.satuan,
                            resep.bahan_baku_id.satuan,
                            resep.bahan_baku_id.name,
                        )
                        resep.bahan_baku_id.stok_saat_ini -= kebutuhan_stok
                record.status_pesanan = 'confirmed'

                low_stock_bahan = record.detail_pesanan_ids.mapped('menu_id.resep_ids.bahan_baku_id').filtered(
                    lambda b: b.stok_saat_ini <= b.reorder_point
                )
                _logger.warning("JANARI DEBUG: low_stock_bahan = %s", low_stock_bahan.mapped('name'))
                if low_stock_bahan:
                    nama_bahan = ', '.join(low_stock_bahan.mapped('name'))
                    channel = self.env['discuss.channel'].sudo().search(
                        [('name', '=', 'general')], limit=1
                    )
                    _logger.warning("JANARI DEBUG: channel = %s", channel)
                    if channel:
                        channel.sudo().message_post(
                            body=f'⚠️ Peringatan Stok Rendah: Stok berikut di bawah reorder point: {nama_bahan}',
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                        )
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Peringatan Stok Rendah',
                            'message': f'Stok berikut di bawah reorder point: {nama_bahan}',
                            'type': 'warning',
                            'sticky': True,
                        }
                    }

# D-06 Tabel Detail Pesanan
class DetailPesanan(models.Model):
    _name = 'janari.detail.pesanan'
    _description = 'Tabel Detail Pesanan'

    pesanan_id = fields.Many2one('janari.pesanan', string='Pesanan Reference', required=True, ondelete='cascade')
    menu_id = fields.Many2one('janari.menu', string='Menu', required=True)
    jumlah = fields.Integer(string='Jumlah', default=1, required=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    status_item = fields.Selection([
        ('ordered', 'Ordered'),
        ('processed', 'Processed'),
        ('done', 'Done')
    ], string='Status Dapur (KDS)', default='ordered')

    @api.depends('menu_id', 'jumlah')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.menu_id.harga_menu * record.jumlah

# D-07 Tabel Transaksi
class Transaksi(models.Model):
    _name = 'janari.transaksi'
    _description = 'Tabel Transaksi'

    pesanan_id = fields.Many2one('janari.pesanan', string='Pesanan', required=True)
    metode_pembayaran = fields.Selection([
        ('cash', 'Tunai'),
        ('qris', 'QRIS')
    ], string='Metode Pembayaran', required=True)
    waktu_transaksi = fields.Datetime(string='Waktu Transaksi', default=fields.Datetime.now)
    total_bayar = fields.Float(string='Total Bayar')

# D-08 Tabel Update Status
class UpdateStatus(models.Model):
    _name = 'janari.update.status'
    _description = 'Tabel Riwayat Perubahan Status KDS'

    detail_pesanan_id = fields.Many2one('janari.detail.pesanan', string='Item Pesanan', required=True)
    status_before = fields.Char(string='Status Sebelum')
    status_after = fields.Char(string='Status Sesudah')

class JanariUser(models.Model):
    _inherit = 'res.users'

    janari_role = fields.Selection([
        ('kasir', 'Staf Kasir'),
        ('packer', 'Staf Packer'),
        ('dapur', 'Staf Dapur'),
        ('kepala_staf', 'Kepala Staf'),
        ('pemilik', 'Pemilik')
    ], string='Role Sistem Janari')