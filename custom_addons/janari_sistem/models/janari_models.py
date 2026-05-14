from odoo import models, fields, api
from odoo.exceptions import UserError

# D-01 Tabel Bahan Baku
class BahanBaku(models.Model):
    _name = 'janari.bahan.baku'
    _description = 'Tabel Bahan Baku'

    name = fields.Char(string='Nama Bahan', required=True)
    jenis = fields.Char(string='Jenis')
    satuan = fields.Char(string='Satuan')
    harga = fields.Float(string='Harga')
    vendor = fields.Char(string='Vendor')
    stok_saat_ini = fields.Integer(string='Stok Saat Ini', default=0)
    reorder_point = fields.Integer(string='Reorder Point', default=10)
    is_low_stock = fields.Boolean(string="Status Stok Rendah", compute="_compute_low_stock", store=True)

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

# D-05 Tabel Pesanan
class Pesanan(models.Model):
    _name = 'janari.pesanan'
    _description = 'Tabel Pesanan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='ID Pesanan', required=True, copy=False, readonly=True, default=lambda self: 'New')
    tanggal_pesanan = fields.Datetime(string='Tanggal Pesanan', default=fields.Datetime.now)
    nomor_meja = fields.Char(string='Nomor Meja / Antrean')
    sumber_pesanan = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online')
    ], string='Sumber Pesanan', default='offline')
    status_pesanan = fields.Selection([
        ('draft', 'Menunggu Pembayaran'),
        ('confirmed', 'Terkonfirmasi'),
        ('done', 'Selesai')
    ], string='Status Keseluruhan', default='draft', tracking=True)
    total_harga = fields.Float(string='Total Harga', compute='_compute_total', store=True)
    detail_pesanan_ids = fields.One2many('janari.detail.pesanan', 'pesanan_id', string='Detail Item')

    @api.depends('detail_pesanan_ids.subtotal')
    def _compute_total(self):
        for record in self:
            record.total_harga = sum(item.subtotal for item in record.detail_pesanan_ids)

    def action_confirm(self):
        for record in self:
            if record.status_pesanan == 'draft':
                record.status_pesanan = 'confirmed'

# D-06 Tabel Detail Pesanan
class DetailPesanan(models.Model):
    _name = 'janari.detail.pesanan'
    _description = 'Tabel Detail Pesanan'
    _order = 'pesanan_id asc, id asc'

    pesanan_id = fields.Many2one('janari.pesanan', string='Pesanan Reference', required=True, ondelete='cascade')
    menu_id = fields.Many2one('janari.menu', string='Menu', required=True)
    jumlah = fields.Integer(string='Jumlah', default=1, required=True)
    catatan = fields.Char(string='Catatan Khusus')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    status_item = fields.Selection([
        ('ordered', 'Ordered'),
        ('processed', 'Processed'),
        ('done', 'Done')
    ], string='Status Dapur (KDS)', default='ordered')
    processed_at = fields.Datetime(string='Waktu Mulai Proses', readonly=True)
    done_at = fields.Datetime(string='Waktu Selesai', readonly=True)
    durasi_tunggu = fields.Integer(
        string='Durasi Tunggu (menit)',
        compute='_compute_durasi',
        store=False,
    )
    update_status_ids = fields.One2many('janari.update.status', 'detail_pesanan_id', string='Riwayat Status')

    # Related fields untuk ditampilkan di KDS kanban card
    nomor_meja = fields.Char(related='pesanan_id.nomor_meja', string='Nomor Meja', store=False, readonly=True)
    tanggal_pesanan = fields.Datetime(related='pesanan_id.tanggal_pesanan', string='Waktu Pesanan', store=False, readonly=True)

    @api.depends('menu_id', 'jumlah')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.menu_id.harga_menu * record.jumlah

    @api.depends('pesanan_id.tanggal_pesanan')
    def _compute_durasi(self):
        now = fields.Datetime.now()
        for record in self:
            if record.pesanan_id and record.pesanan_id.tanggal_pesanan:
                delta = now - record.pesanan_id.tanggal_pesanan
                record.durasi_tunggu = int(delta.total_seconds() / 60)
            else:
                record.durasi_tunggu = 0

    def write(self, vals):
        if 'status_item' in vals:
            logs = []
            for record in self:
                if record.status_item != vals['status_item']:
                    logs.append({
                        'detail_pesanan_id': record.id,
                        'status_before': record.status_item,
                        'status_after': vals['status_item'],
                        'updated_by': self.env.user.id,
                        'updated_at': fields.Datetime.now(),
                    })
            result = super().write(vals)
            for log_vals in logs:
                self.env['janari.update.status'].create(log_vals)
            return result
        return super().write(vals)

    def action_mulai_proses(self):
        for record in self:
            if record.status_item != 'ordered':
                raise UserError('Hanya item dengan status "Ordered" yang bisa diproses.')
            record.write({
                'status_item': 'processed',
                'processed_at': fields.Datetime.now(),
            })

    def action_selesaikan(self):
        for record in self:
            if record.status_item != 'processed':
                raise UserError('Hanya item dengan status "Processed" yang bisa diselesaikan.')
            record.write({
                'status_item': 'done',
                'done_at': fields.Datetime.now(),
            })
            pesanan = record.pesanan_id
            if all(item.status_item == 'done' for item in pesanan.detail_pesanan_ids):
                pesanan.status_pesanan = 'done'
                pesanan.message_post(
                    body=f'Pesanan <b>{pesanan.name}</b> (Meja {pesanan.nomor_meja or "-"}) sudah selesai dan siap diserahkan ke pelanggan.',
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )

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
    _order = 'updated_at desc'

    detail_pesanan_id = fields.Many2one('janari.detail.pesanan', string='Item Pesanan', required=True, ondelete='cascade')
    status_before = fields.Char(string='Status Sebelum')
    status_after = fields.Char(string='Status Sesudah')
    updated_by = fields.Many2one('res.users', string='Diubah Oleh', default=lambda self: self.env.user)
    updated_at = fields.Datetime(string='Waktu Perubahan', default=fields.Datetime.now)
    note = fields.Char(string='Catatan')

class JanariUser(models.Model):
    _inherit = 'res.users'

    janari_role = fields.Selection([
        ('kasir', 'Staf Kasir'),
        ('packer', 'Staf Packer'),
        ('dapur', 'Staf Dapur'),
        ('kepala_staf', 'Kepala Staf'),
        ('pemilik', 'Pemilik')
    ], string='Role Sistem Janari')
