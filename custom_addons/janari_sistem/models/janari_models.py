from odoo import models, fields, api

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

    def action_confirm(self):
        for record in self:
            if record.status_pesanan == 'draft':
                record.status_pesanan = 'confirmed'

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

    @api.model_create_multi
    def create(self, vals_list):
        users = super(JanariUser, self).create(vals_list)
        for user in users:
            user._update_janari_groups()
        return users

    def write(self, vals):
        res = super(JanariUser, self).write(vals)
        if 'janari_role' in vals:
            self._update_janari_groups()
        return res

    def _update_janari_groups(self):
        for user in self:
            group_map = {
                'kasir': 'janari_sistem.group_janari_kasir',
                'packer': 'janari_sistem.group_janari_packer',
                'dapur': 'janari_sistem.group_janari_dapur',
                'kepala_staf': 'janari_sistem.group_janari_kepala_staf',
                'pemilik': 'janari_sistem.group_janari_pemilik',
            }

            # hapus semua grup Janari agar tidak double role
            all_janari_groups = [self.env.ref(xml_id).id for xml_id in group_map.values() if self.env.ref(xml_id, raise_if_not_found=False)]
            user.write({'groups_id': [(3, gid) for gid in all_janari_groups]})

            if user.janari_role and user.janari_role in group_map:
                group_xml_id = group_map[user.janari_role]
                group = self.env.ref(group_xml_id, raise_if_not_found=False)
                if group:
                    user.write({'groups_id': [(4, group.id)]})